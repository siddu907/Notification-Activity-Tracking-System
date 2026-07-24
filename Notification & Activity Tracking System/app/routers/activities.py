from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, inspect, literal_column
from datetime import datetime, timedelta
from typing import List

from app.database import SessionLocal
from app.models import ActivityLog, AuditLog, User, ActionEnum, Project, Task, ProjectMember
from app.schemas import ActivityLogRead, AuditLogRead
from app.utils import verify_token, verify_admin_or_manager

router = APIRouter()
audit_router = APIRouter()


def _table_has_column(table_name: str, column_name: str, db: Session) -> bool:
    try:
        inspector = inspect(db.bind)
        return column_name in {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _activity_columns(db: Session):
    columns = [
        ActivityLog.id,
        ActivityLog.user_id,
        literal_column("action").label("action"),
    ]

    if _table_has_column("activity_logs", "entity_type", db):
        columns.append(ActivityLog.entity_type)
    elif _table_has_column("activity_logs", "target_type", db):
        columns.append(literal_column("target_type").label("entity_type"))
    else:
        columns.append(literal_column("NULL").label("entity_type"))

    if _table_has_column("activity_logs", "entity_id", db):
        columns.append(ActivityLog.entity_id)
    elif _table_has_column("activity_logs", "target_id", db):
        columns.append(literal_column("target_id").label("entity_id"))
    else:
        columns.append(literal_column("NULL").label("entity_id"))

    if _table_has_column("activity_logs", "description", db):
        columns.append(ActivityLog.description)
    else:
        columns.append(literal_column("NULL").label("description"))

    if _table_has_column("activity_logs", "created_at", db):
        columns.append(ActivityLog.created_at)
    else:
        columns.append(literal_column("CURRENT_TIMESTAMP").label("created_at"))

    if _table_has_column("activity_logs", "is_deleted", db):
        columns.append(ActivityLog.is_deleted)
    else:
        columns.append(literal_column("0").label("is_deleted"))

    return columns


def _serialize_activity_row(row, performed_by: dict | None = None) -> dict:
    payload = {
        "id": getattr(row, "id", None),
        "user_id": getattr(row, "user_id", None),
        "performed_by": performed_by,
        "action": getattr(row, "action", None),
        "entity_id": getattr(row, "entity_id", None),
        "description": getattr(row, "description", None),
        "created_at": getattr(row, "created_at", None),
    }
    payload["entity_type"] = getattr(row, "entity_type", None)
    return payload


def _build_performed_by_map(db: Session, activity_rows) -> dict:
    user_ids = [getattr(row, "user_id", None) for row in activity_rows if getattr(row, "user_id", None) is not None]
    if not user_ids:
        return {}

    users = db.query(User.id, User.full_name, User.role).filter(User.id.in_(user_ids)).all()
    return {
        user.id: {
            "id": user.id,
            "full_name": user.full_name,
            "role": user.role,
        }
        for user in users
    }


@router.get("", response_model=List[ActivityLogRead])
def get_all_activities(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    action: str = Query(None),
    entity_type: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can view all activities"
        )
    
    query = db.query(*_activity_columns(db))
    if _table_has_column("activity_logs", "is_deleted", db):
        query = query.filter(ActivityLog.is_deleted == False)

    if entity_type:
        if _table_has_column("activity_logs", "entity_type", db):
            query = query.filter(ActivityLog.entity_type == entity_type)
        elif _table_has_column("activity_logs", "target_type", db):
            query = query.filter(literal_column("target_type") == entity_type)
    
    if action:
        try:
            action_enum = ActionEnum[action]
            query = query.filter(ActivityLog.action == action_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    if start_date:
        query = query.filter(ActivityLog.created_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(ActivityLog.created_at < end_date_end)
    
    activities = query.order_by(desc(ActivityLog.created_at)).offset(skip).limit(limit).all()
    performed_by_map = _build_performed_by_map(db, activities)

    return [
        _serialize_activity_row(activity, performed_by_map.get(getattr(activity, "user_id", None)))
        for activity in activities
    ]


@router.get("/user/{user_id}", response_model=List[ActivityLogRead])
def get_user_activities(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    action: str = Query(None),
    entity_type: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Check permissions
    if current_user.id != user_id:
        if current_user.role.value not in ["Admin", "Manager"]:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own activities"
            )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(*_activity_columns(db)).filter(
        ActivityLog.user_id == user_id,
    )
    if _table_has_column("activity_logs", "is_deleted", db):
        query = query.filter(ActivityLog.is_deleted == False)

    if entity_type:
        if _table_has_column("activity_logs", "entity_type", db):
            query = query.filter(ActivityLog.entity_type == entity_type)
        elif _table_has_column("activity_logs", "target_type", db):
            query = query.filter(literal_column("target_type") == entity_type)
    
    # Apply filters
    if action:
        try:
            action_enum = ActionEnum[action]
            query = query.filter(ActivityLog.action == action_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    if start_date:
        query = query.filter(ActivityLog.created_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(ActivityLog.created_at < end_date_end)
    
    activities = query.order_by(desc(ActivityLog.created_at)).offset(skip).limit(limit).all()
    performed_by_map = _build_performed_by_map(db, activities)

    return [
        _serialize_activity_row(activity, performed_by_map.get(getattr(activity, "user_id", None)))
        for activity in activities
    ]


@router.get("/project/{project_id}", response_model=List[ActivityLogRead])
def get_project_activities(
    project_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    action: str = Query(None),
    entity_type: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
   
    # Verify project exists and user has access
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is project member or admin
    if current_user.role.value != "Admin":
        is_member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        ).first() is not None

        if not is_member and current_user.id != project.created_by:
            raise HTTPException(
                status_code=403,
                detail="You are not a member of this project"
            )
    
    query = db.query(*_activity_columns(db))
    if _table_has_column("activity_logs", "is_deleted", db):
        query = query.filter(ActivityLog.is_deleted == False)
    
    # Apply filters
    if action:
        try:
            action_enum = ActionEnum[action]
            query = query.filter(ActivityLog.action == action_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    
    task_ids_subquery = db.query(Task.id).filter(Task.project_id == project_id)

    query = query.filter(
        or_(
            and_(ActivityLog.entity_type == "Project", ActivityLog.entity_id == project_id),
            and_(ActivityLog.entity_type == "Task", ActivityLog.entity_id.in_(task_ids_subquery))
        )
    )

    if entity_type:
        if _table_has_column("activity_logs", "entity_type", db):
            query = query.filter(ActivityLog.entity_type == entity_type)
        elif _table_has_column("activity_logs", "target_type", db):
            query = query.filter(literal_column("target_type") == entity_type)
    
    if start_date:
        query = query.filter(ActivityLog.created_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(ActivityLog.created_at < end_date_end)
    
    activities = query.order_by(desc(ActivityLog.created_at)).offset(skip).limit(limit).all()
    performed_by_map = _build_performed_by_map(db, activities)

    return [
        _serialize_activity_row(activity, performed_by_map.get(getattr(activity, "user_id", None)))
        for activity in activities
    ]


@audit_router.get("/audit-logs", tags=["Audit Logs"], response_model=List[AuditLogRead])
def get_all_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    entity_type: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
   
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can view audit logs"
        )
    
    query = db.query(AuditLog).filter(AuditLog.is_deleted == False)
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    
    if start_date:
        query = query.filter(AuditLog.changed_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(AuditLog.changed_at < end_date_end)
    
    audit_logs = query.order_by(desc(AuditLog.changed_at)).offset(skip).limit(limit).all()
    
    return audit_logs


@audit_router.get("/audit-logs/{entity_type}/{entity_id}", tags=["Audit Logs"], response_model=List[AuditLogRead])
def get_entity_audit_logs(
    entity_type: str,
    entity_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify entity exists (for Task)
    if entity_type == "Task":
        task = db.query(Task).filter(Task.id == entity_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Check user has access to the task's project
        if current_user.role.value != "Admin":
            project = db.query(Project).filter(Project.id == task.project_id).first()
            if current_user.id != project.created_by:
                # Check if user is member
                from app.models import ProjectMember
                is_member = db.query(ProjectMember).filter(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == current_user.id
                ).first()
                if not is_member:
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have access to this task"
                    )
    
    elif entity_type == "Project":
        project = db.query(Project).filter(Project.id == entity_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Check user has access
        if current_user.role.value != "Admin":
            if current_user.id != project.created_by:
                from app.models import ProjectMember
                is_member = db.query(ProjectMember).filter(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == current_user.id
                ).first()
                if not is_member:
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have access to this project"
                    )
    
    audit_logs = db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id,
        AuditLog.is_deleted == False
    ).order_by(desc(AuditLog.changed_at)).offset(skip).limit(limit).all()
    
    return audit_logs



