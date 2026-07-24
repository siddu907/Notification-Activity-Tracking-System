from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app import schemas, models
from app.utils import get_db, get_current_user, require_roles, is_project_member
from app.services import create_activity_log, create_notification, check_notification_preference
from app.models import ActionEnum, NotificationTypeEnum

router = APIRouter()

def _member_response(membership: models.ProjectMember) -> dict:
    return {
        "id": membership.id,
        "project_id": membership.project_id,
        "project_name": membership.project.name,
        "user_id": membership.user_id,
        "full_name": membership.user.full_name,
        "role": membership.user.role,
    }


@router.post("/{project_id}/members", response_model=schemas.ProjectMemberRead)
def add_member(
    project_id: int,
    membership_in: schemas.ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("Admin", "Manager")),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role == models.RoleEnum.manager and not is_project_member(current_user.id, project_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    existing = db.query(models.ProjectMember).filter(
        models.ProjectMember.project_id == project_id,
        models.ProjectMember.user_id == membership_in.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already a project member")
    # Ensure the user exists to avoid FK integrity errors
    user = db.query(models.User).filter(models.User.id == membership_in.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    membership = models.ProjectMember(project_id=project_id, user_id=membership_in.user_id)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    
    # Log activity
    try:
        added_user = db.query(models.User).filter(models.User.id == membership_in.user_id).first()
        if added_user:
            role_name = added_user.role.value
            description = f"{role_name} '{added_user.full_name}' added to project '{project.name}'"
            create_activity_log(
                db=db,
                user_id=current_user.id,
                action=ActionEnum.member_added,
                entity_type="User",
                entity_id=added_user.id,
                description=description
            )
        
        # Notify new member
        user = added_user
        if user and check_notification_preference(db, user.id, NotificationTypeEnum.new_project_member):
            create_notification(
                db=db,
                user_id=user.id,
                title="Added to Project",
                message=f"You have been added to project '{project.name}'",
                notification_type=NotificationTypeEnum.new_project_member,
                entity_type="Project",
                entity_id=project_id
            )

        # Notify existing project members about the new member addition
        existing_members = db.query(models.ProjectMember).filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.user_id != user.id
        ).all()
        for member in existing_members:
            if check_notification_preference(db, member.user_id, NotificationTypeEnum.new_project_member):
                create_notification(
                    db=db,
                    user_id=member.user_id,
                    title="Project Member Added",
                    message=f"{added_user.full_name} has been added to project '{project.name}'",
                    notification_type=NotificationTypeEnum.new_project_member,
                    entity_type="Project",
                    entity_id=project_id
                )
    except Exception:
        db.rollback()
        pass
    
    return _member_response(membership)


@router.get("/{project_id}/members", response_model=List[schemas.ProjectMemberRead])
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role != models.RoleEnum.admin and not is_project_member(current_user.id, project_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    memberships = db.query(models.ProjectMember).filter(models.ProjectMember.project_id == project_id).all()
    return [_member_response(membership) for membership in memberships]
