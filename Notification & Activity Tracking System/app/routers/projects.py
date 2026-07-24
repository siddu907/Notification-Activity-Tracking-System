from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from app import schemas, models
from app.utils import get_db, get_current_user, require_roles, is_project_member
from app.services import create_activity_log, create_audit_log, track_entity_changes, create_notification, check_notification_preference
from app.models import ActionEnum, NotificationTypeEnum

router = APIRouter()

def _project_response(project: models.Project) -> Dict:
    return {
        "id": project.id,
        "project_id": project.id,
        "project_name": project.name,
        "project_description": project.description,
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at,
        "is_deleted": project.is_deleted,
        "created_by_user": {
            "user_id": project.creator.id,
            "full_name": project.creator.full_name,
            "role": project.creator.role,
        },
    }

@router.post("/", response_model=schemas.ProjectRead)
def create_project(
    project_in: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("Admin", "Manager")),
):
    project = models.Project(
        name=project_in.name,
        description=project_in.description,
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Log activity
    try:
        create_activity_log(
            db=db,
            user_id=current_user.id,
            action=ActionEnum.project_created,
            entity_type="Project",
            entity_id=project.id,
            description=f"Project '{project.name}' created by {current_user.full_name}"
        )
    except Exception:
        db.rollback()
    
    return _project_response(project)

@router.get("/", response_model=List[schemas.ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    search: Optional[str] = Query(None, description="Search by project name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = db.query(models.Project).filter(models.Project.is_deleted == False)
    if current_user.role != models.RoleEnum.admin:
        member_project_ids = [membership.project_id for membership in current_user.memberships]
        query = query.filter(models.Project.id.in_(member_project_ids))
    if project_id is not None:
        query = query.filter(models.Project.id == project_id)
    elif search:
        query = query.filter(models.Project.name.ilike(f"%{search}%"))
    projects = query.offset((page - 1) * page_size).limit(page_size).all()
    return [_project_response(project) for project in projects]

@router.get("/analytics")
def overall_analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("Admin", "Manager")),
):
    projects = db.query(models.Project).filter(models.Project.is_deleted == False).all()
    total_projects = len(projects)
    total_tasks = db.query(models.Task).filter(models.Task.is_deleted == False).count()
    status_counts = {
        status.value: db.query(models.Task).filter(models.Task.status == status, models.Task.is_deleted == False).count()
        for status in models.StatusEnum
    }
    priority_counts = {
        priority.value: db.query(models.Task).filter(models.Task.priority == priority, models.Task.is_deleted == False).count()
        for priority in models.PriorityEnum
    }
    completed_projects = 0
    active_projects = 0
    for project in projects:
        project_tasks = db.query(models.Task).filter(models.Task.project_id == project.id, models.Task.is_deleted == False).all()
        if project_tasks and all(task.status == models.StatusEnum.completed for task in project_tasks):
            completed_projects += 1
        else:
            active_projects += 1
    return {
        "total_projects": total_projects,
        "completed_projects": completed_projects,
        "active_projects": active_projects,
        "total_tasks": total_tasks,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
    }

@router.get("/{project_id}", response_model=schemas.ProjectRead)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role != models.RoleEnum.admin and not is_project_member(current_user.id, project_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return _project_response(project)

@router.put("/{project_id}", response_model=schemas.ProjectRead)
def update_project(
    project_id: int,
    project_in: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role == models.RoleEnum.admin or (current_user.role == models.RoleEnum.manager and is_project_member(current_user.id, project_id, db)):
        old_data = {
            "name": project.name,
            "description": project.description
        }
        
        project.name = project_in.name
        project.description = project_in.description
        db.commit()
        db.refresh(project)
        
        # Log activity
        try:
            create_activity_log(
                db=db,
                user_id=current_user.id,
                action=ActionEnum.project_updated,
                entity_type="Project",
                entity_id=project.id,
                description=f"Project '{project.name}' updated by {current_user.full_name}"
            )
            
            # Track changes in audit log
            track_entity_changes(
                db=db,
                entity_type="Project",
                entity_id=project.id,
                old_data=old_data,
                new_data={"name": project_in.name, "description": project_in.description},
                changed_by=current_user.id
            )
            
            # Notify project members
            members = db.query(models.ProjectMember).filter(
                models.ProjectMember.project_id == project_id
            ).all()
            
            for member in members:
                if member.user_id != current_user.id:
                    if check_notification_preference(db, member.user_id, NotificationTypeEnum.project_updated):
                        create_notification(
                            db=db,
                            user_id=member.user_id,
                            title="Project Updated",
                            message=f"Project '{project.name}' has been updated",
                            notification_type=NotificationTypeEnum.project_updated,
                            entity_type="Project",
                            entity_id=project.id
                        )
        except Exception:
            db.rollback()
        
        return _project_response(project)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


@router.get("/{project_id}/analytics")
def project_analytics(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role != models.RoleEnum.admin and not is_project_member(current_user.id, project_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    total_tasks = db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.is_deleted == False).count()
    status_counts = {
        status.value: db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.status == status, models.Task.is_deleted == False).count()
        for status in models.StatusEnum
    }
    priority_counts = {
        priority.value: db.query(models.Task).filter(models.Task.project_id == project_id, models.Task.priority == priority, models.Task.is_deleted == False).count()
        for priority in models.PriorityEnum
    }
    completed_tasks = status_counts.get(models.StatusEnum.completed.value, 0)
    pending_tasks = status_counts.get(models.StatusEnum.pending.value, 0)
    in_progress_tasks = status_counts.get(models.StatusEnum.in_progress.value, 0)
    overdue_tasks = db.query(models.Task).filter(
        models.Task.project_id == project_id,
        models.Task.is_deleted == False,
        models.Task.due_date != None,
        models.Task.due_date < datetime.now(timezone.utc),
        models.Task.status != models.StatusEnum.completed,
    ).count()
    project_priority = None
    if priority_counts[models.PriorityEnum.high.value] > 0:
        project_priority = models.PriorityEnum.high.value
    elif priority_counts[models.PriorityEnum.medium.value] > 0:
        project_priority = models.PriorityEnum.medium.value
    elif priority_counts[models.PriorityEnum.low.value] > 0:
        project_priority = models.PriorityEnum.low.value
    member_count = db.query(models.ProjectMember).filter(models.ProjectMember.project_id == project_id).count()
    return {
        "project_id": project_id,
        "total_tasks": total_tasks,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "in_progress_tasks": in_progress_tasks,
        "overdue_tasks": overdue_tasks,
        "project_priority": project_priority,
        "member_count": member_count,
    }

@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("Admin")),
):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.is_deleted == False).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project.is_deleted = True
    db.commit()
    
    # Log activity
    try:
        create_activity_log(
            db=db,
            user_id=current_user.id,
            action=ActionEnum.project_deleted,
            entity_type="Project",
            entity_id=project_id,
            description=f"Project deleted by {current_user.full_name}"
        )
    except Exception:
        db.rollback()
    
    return {"detail": "Project deleted"}
