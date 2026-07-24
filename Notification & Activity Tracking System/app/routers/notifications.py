from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import List

from app.database import SessionLocal
from app.models import Notification, NotificationPreference, User
from app.schemas import NotificationPreferenceRead, NotificationPreferenceUpdate, NotificationRead, NotificationUpdate
from app.services import create_default_notification_preference
from app.utils import verify_token
from sqlalchemy import inspect
from types import SimpleNamespace

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _table_has_column(table_name: str, column_name: str, db: Session) -> bool:
    try:
        inspector = inspect(db.bind)
        return column_name in {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return False


def _notification_query(db: Session):
    # Return a query selecting only the columns that exist in the current DB table
    cols = [Notification.id, Notification.user_id]

    # optional text fields
    if _table_has_column("notifications", "title", db):
        cols.append(Notification.title)
    if _table_has_column("notifications", "message", db):
        cols.append(Notification.message)

    # optional metadata
    if _table_has_column("notifications", "notification_type", db):
        cols.append(Notification.notification_type)
    if _table_has_column("notifications", "entity_type", db):
        cols.append(Notification.entity_type)
    if _table_has_column("notifications", "entity_id", db):
        cols.append(Notification.entity_id)

    # read flags / timestamps
    if _table_has_column("notifications", "is_read", db):
        cols.append(Notification.is_read)
    if _table_has_column("notifications", "read_at", db):
        cols.append(Notification.read_at)
    if _table_has_column("notifications", "created_at", db):
        cols.append(Notification.created_at)

    return db.query(*cols)


def _notification_row_to_object(row):
    # Convert SQLAlchemy row/tuple into an object with attributes expected by NotificationRead
    if hasattr(row, "_mapping"):
        data = dict(row._mapping)
        return SimpleNamespace(**data)
    if isinstance(row, tuple):
        obj = {
            "id": row[0] if len(row) > 0 else None,
            "user_id": row[1] if len(row) > 1 else None,
            "title": None,
            "message": None,
            "notification_type": None,
            "entity_type": None,
            "entity_id": None,
            "is_read": False,
            "read_at": None,
            "created_at": None,
        }
        idx = 2
        while idx < len(row):
            v = row[idx]
            if isinstance(v, bool):
                obj["is_read"] = v
            elif isinstance(v, int) and obj.get("entity_id") is None and v not in (obj["id"], obj["user_id"]):
                obj["entity_id"] = v
            elif hasattr(v, "strftime") and obj.get("created_at") is None:
                obj["created_at"] = v
            elif isinstance(v, str):
                if obj.get("title") is None:
                    obj["title"] = v
                elif obj.get("message") is None:
                    obj["message"] = v
                elif obj.get("notification_type") is None:
                    obj["notification_type"] = v
                elif obj.get("entity_type") is None:
                    obj["entity_type"] = v
            idx += 1
        return SimpleNamespace(**obj)
    if hasattr(row, "__dict__"):
        data = {k: v for k, v in vars(row).items() if not k.startswith("_")}
        return SimpleNamespace(**data)
    return SimpleNamespace(id=None)


@router.get("", response_model=List[NotificationRead])
def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    is_read: bool = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    query = _notification_query(db).filter(Notification.user_id == current_user.id)
    if _table_has_column("notifications", "is_deleted", db):
        query = query.filter(Notification.is_deleted == False)

    if is_read is not None and _table_has_column("notifications", "is_read", db):
        query = query.filter(Notification.is_read == is_read)

    # order_by uses created_at only if present
    if _table_has_column("notifications", "created_at", db):
        query = query.order_by(desc(Notification.created_at))

    rows = query.offset(skip).limit(limit).all()
    notifications = [_notification_row_to_object(r) for r in rows]
    return notifications


@router.get("/preferences", response_model=NotificationPreferenceRead)
def get_notification_preferences(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not pref:
        pref = create_default_notification_preference(db, current_user.id)
    return pref


@router.put("/preferences", response_model=NotificationPreferenceRead)
def update_notification_preferences(
    preference_update: NotificationPreferenceUpdate,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == current_user.id).first()
    if not pref:
        pref = create_default_notification_preference(db, current_user.id)

    update_data = preference_update.model_dump(exclude_unset=True)
    normalized_updates = {}
    for key, value in update_data.items():
        if key == "project_member":
            normalized_updates["new_project_member"] = value
        else:
            normalized_updates[key] = value

    for key, value in normalized_updates.items():
        setattr(pref, key, value)

    db.commit()
    db.refresh(pref)
    return pref


@router.get("/unread", response_model=List[NotificationRead])
def get_unread_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    query = _notification_query(db).filter(Notification.user_id == current_user.id)
    if _table_has_column("notifications", "is_deleted", db):
        query = query.filter(Notification.is_deleted == False)
    if _table_has_column("notifications", "is_read", db):
        query = query.filter(Notification.is_read == False)
    if _table_has_column("notifications", "created_at", db):
        query = query.order_by(desc(Notification.created_at))

    rows = query.offset(skip).limit(limit).all()
    return [_notification_row_to_object(r) for r in rows]



@router.put("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # fetch with schema-safe query
    row = _notification_query(db).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
        Notification.is_deleted == False
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")

    obj = _notification_row_to_object(row)

    # Only attempt to update DB columns if they exist
    can_update_is_read = _table_has_column("notifications", "is_read", db)
    can_update_read_at = _table_has_column("notifications", "read_at", db)

    if can_update_is_read and not getattr(obj, "is_read", False):
        updates = {}
        updates[Notification.is_read] = True
        if can_update_read_at:
            updates[Notification.read_at] = datetime.utcnow()
        db.query(Notification).filter(Notification.id == notification_id).update(updates)
        db.commit()
        # re-read using safe query
        row = _notification_query(db).filter(Notification.id == notification_id).first()
        return _notification_row_to_object(row)

    return obj


@router.put("/read-all", response_model=dict)
def mark_all_notifications_as_read(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Use schema-safe query to find unread notifications
    query = _notification_query(db).filter(
        Notification.user_id == current_user.id,
        Notification.is_deleted == False,
    )
    if _table_has_column("notifications", "is_read", db):
        query = query.filter(Notification.is_read == False)

    rows = query.all()
    count = len(rows)

    can_update_is_read = _table_has_column("notifications", "is_read", db)
    can_update_read_at = _table_has_column("notifications", "read_at", db)

    if can_update_is_read:
        updates = {Notification.is_read: True}
        if can_update_read_at:
            updates[Notification.read_at] = datetime.utcnow()
        filters = [Notification.user_id == current_user.id]
        if _table_has_column("notifications", "is_deleted", db):
            filters.append(Notification.is_deleted == False)
        filters.append(Notification.is_read == False)
        db.query(Notification).filter(*filters).update(updates, synchronize_session=False)
        db.commit()

    return {"message": f"Marked {count} notifications as read", "updated_count": count}



@router.delete("/{notification_id}", response_model=dict)
def delete_notification(
    notification_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    row = _notification_query(db).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    )
    if _table_has_column("notifications", "is_deleted", db):
        row = row.filter(Notification.is_deleted == False)
    row = row.first()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")

    # If is_deleted column exists, soft-delete; otherwise, delete the row
    if _table_has_column("notifications", "is_deleted", db):
        db.query(Notification).filter(Notification.id == notification_id).update({Notification.is_deleted: True})
    else:
        db.query(Notification).filter(Notification.id == notification_id).delete()
    db.commit()
    return {"message": "Notification deleted successfully"}



