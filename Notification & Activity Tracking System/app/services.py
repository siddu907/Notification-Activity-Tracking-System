"""
Services module for handling notifications, activity logs, and audit trails.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from app.models import (
    ActivityLog, Notification, AuditLog, NotificationPreference,
    ActionEnum, NotificationTypeEnum, RoleEnum, Task, User
)
from app.schemas import (
    ActivityLogCreate, NotificationCreate, AuditLogCreate
)
from typing import Optional, Dict, Any


# ============== Activity Log Service ==============

def _table_has_column(table_name: str, column_name: str, db: Session) -> bool:
    try:
        inspector = inspect(db.bind)
        return column_name in {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return False


def create_activity_log(
    db: Session,
    user_id: int,
    action: ActionEnum,
    entity_type: str,
    entity_id: int,
    description: Optional[str] = None
) -> ActivityLog:
    """
    Create an activity log entry.
    
    Args:
        db: Database session
        user_id: ID of the user performing the action
        action: Action type
        entity_type: Type of entity affected (e.g., "Task", "Project")
        entity_id: ID of the entity
        description: Optional description of the action
    
    Returns:
        Created ActivityLog object
    """
    # If caller didn't provide a description, generate a sensible default
    if description is None:
        action_text = getattr(action, "value", action)
        if entity_type:
            description = f"{action_text} on {entity_type} {entity_id}"
        else:
            description = f"{action_text}"
    if _table_has_column("activity_logs", "entity_type", db):
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description
        )
    else:
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            entity_id=entity_id,
            description=description
        )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    try:
        if action != ActionEnum.user_login:
            _notify_admins_for_action(
                db=db,
                actor_id=user_id,
                action=action,
                description=description,
                entity_type=entity_type,
                entity_id=entity_id,
            )
    except Exception:
        pass

    return activity


def _notify_admins_for_action(
    db: Session,
    actor_id: int,
    action: ActionEnum,
    description: str,
    entity_type: str,
    entity_id: int,
) -> None:
    """Send a notification to all admin users for every action."""
    admins = db.query(User).filter(User.role == RoleEnum.admin, User.is_deleted == False).all()
    title = f"{action.value}"
    message = description

    for admin in admins:
        if admin.id == actor_id:
            continue
        create_notification(
            db=db,
            user_id=admin.id,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
        )


# ============== Notification Service ==============

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: Optional[NotificationTypeEnum] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None
) -> Notification:
    """
    Create a notification for a user.
    
    Args:
        db: Database session
        user_id: ID of the user to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        entity_type: Type of entity (optional)
        entity_id: ID of entity (optional)
    
    Returns:
        Created Notification object
    """
    if _table_has_column("notifications", "title", db):
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id
        )
    else:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id
        )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def check_notification_preference(
    db: Session,
    user_id: int,
    notification_type: NotificationTypeEnum
) -> bool:
    """Return whether a notification type is enabled for the given user."""
    pref = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()

    if not pref:
        pref = create_default_notification_preference(db, user_id)

    preference_map = {
        NotificationTypeEnum.task_assigned: bool(pref.task_assigned),
        NotificationTypeEnum.task_reassigned: bool(pref.task_reassigned),
        NotificationTypeEnum.task_deadline_updated: bool(pref.task_deadline_updated),
        NotificationTypeEnum.new_project_member: bool(pref.new_project_member),
        NotificationTypeEnum.project_updated: bool(pref.project_updated),
        NotificationTypeEnum.task_completed: bool(pref.task_completed),
    }

    if notification_type in preference_map:
        return preference_map[notification_type]

    return True


def create_default_notification_preference(
    db: Session,
    user_id: int
) -> NotificationPreference:
    """Create default notification preferences for a user."""
    pref = NotificationPreference(user_id=user_id)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


# ============== Audit Log Service ==============

def create_audit_log(
    db: Session,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    changed_by: Optional[int] = None
) -> AuditLog:
    """
    Create an audit log entry for tracking changes.
    
    Args:
        db: Database session
        entity_type: Type of entity that changed
        entity_id: ID of the entity
        field_name: Name of the field that changed
        old_value: Previous value
        new_value: New value
        changed_by: ID of user who made the change
    
    Returns:
        Created AuditLog object
    """
    audit = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_by=changed_by
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def track_entity_changes(
    db: Session,
    entity_type: str,
    entity_id: int,
    old_data: Dict[str, Any],
    new_data: Dict[str, Any],
    changed_by: int
) -> list:
    """
    Track multiple field changes for an entity.
    
    Args:
        db: Database session
        entity_type: Type of entity
        entity_id: ID of the entity
        old_data: Dictionary of old values
        new_data: Dictionary of new values
        changed_by: ID of user making changes
    
    Returns:
        List of created AuditLog objects
    """
    audit_logs = []
    
    # Check for modified fields
    for field, new_value in new_data.items():
        old_value = old_data.get(field)
        if old_value != new_value:
            audit_log = create_audit_log(
                db=db,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field,
                old_value=old_value,
                new_value=new_value,
                changed_by=changed_by
            )
            audit_logs.append(audit_log)
    
    return audit_logs


