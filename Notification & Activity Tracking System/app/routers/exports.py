from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import inspect, literal_column
from datetime import datetime, timedelta
import csv
import io
import json
from types import SimpleNamespace
from typing import Optional, List

from app.database import SessionLocal
from app.models import ActivityLog, AuditLog, User, ActionEnum
from app.utils import verify_token

router = APIRouter()


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


def _normalize_activity_action_filter(action: Optional[str]) -> Optional[str]:
    if not action:
        return None

    candidate = action.strip()
    if candidate in ActionEnum.__members__:
        return ActionEnum[candidate].name

    try:
        return ActionEnum(candidate).name
    except ValueError:
        normalized = candidate.lower().replace(" ", "_")
        if normalized in ActionEnum.__members__:
            return ActionEnum[normalized].name
        return candidate


def _clean_optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return int(value)


def _display_activity_action(action: Optional[str]) -> Optional[str]:
    if action is None:
        return None

    if isinstance(action, ActionEnum):
        return action.value

    candidate = str(action).strip()
    if candidate in ActionEnum.__members__:
        return ActionEnum[candidate].value

    try:
        return ActionEnum(candidate).value
    except ValueError:
        normalized = candidate.lower().replace(" ", "_")
        if normalized in ActionEnum.__members__:
            return ActionEnum[normalized].value
        return candidate


def _activity_query(db: Session):
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

    return db.query(*columns)


def _activity_row_to_object(row) -> SimpleNamespace:
    if isinstance(row, tuple):
        if len(row) == 6:
            activity_id, user_id, action, entity_id, description, created_at = row
            entity_type = None
        else:
            activity_id, user_id, action, entity_type, entity_id, description, created_at = row
        return SimpleNamespace(
            id=activity_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            created_at=created_at,
        )
    return row


@router.get("/activities/csv")
def export_activities_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can export logs"
        )
    
    # Build query
    query = _activity_query(db)
    if _table_has_column("activity_logs", "is_deleted", db):
        query = query.filter(ActivityLog.is_deleted == False)
    
    if action:
        action_filter = _normalize_activity_action_filter(action)
        query = query.filter(literal_column("action") == action_filter)
    
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
    
    activities = [_activity_row_to_object(row) for row in query.order_by(ActivityLog.created_at).all()]
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'User ID', 'User Name', 'Action', 'Entity Type', 'Entity ID', 'Description', 'Created At'])
    
    # Write data
    for activity in activities:
        user = db.query(User).filter(User.id == activity.user_id).first()
        user_name = user.full_name if user else 'Unknown'
        action_value = _display_activity_action(getattr(activity, 'action', None))

        writer.writerow([
            activity.id,
            activity.user_id,
            user_name,
            action_value,
            getattr(activity, "entity_type", None) or "",
            activity.entity_id,
            activity.description or '',
            activity.created_at.strftime('%Y-%m-%d %H:%M:%S') if activity.created_at else ''
        ])
    
    # Create response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=activities_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/audit-logs/csv")
def export_audit_logs_csv(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can export logs"
        )
    
    # Build query
    query = db.query(AuditLog).filter(AuditLog.is_deleted == False)
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    
    if start_date:
        query = query.filter(AuditLog.changed_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(AuditLog.changed_at < end_date_end)
    
    audit_logs = query.order_by(AuditLog.changed_at).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'Entity Type', 'Entity ID', 'Field Name', 'Old Value', 'New Value', 'Changed By', 'Changed At'])
    
    # Write data
    for audit in audit_logs:
        user = db.query(User).filter(User.id == audit.changed_by).first()
        user_name = user.full_name if user else 'Unknown'
        
        writer.writerow([
            audit.id,
            audit.entity_type,
            audit.entity_id,
            audit.field_name,
            audit.old_value or '',
            audit.new_value or '',
            user_name,
            audit.changed_at.strftime('%Y-%m-%d %H:%M:%S') if audit.changed_at else ''
        ])
    
    # Create response
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )



def _build_pdf_bytes(title: str, headers: List[str], rows: List[List[str]]) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    page = landscape(letter)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page,
        rightMargin=18,
        leftMargin=18,
        topMargin=24,
        bottomMargin=24,
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    body_style.fontSize = 8
    body_style.leading = 10
    story = [Paragraph(title, title_style), Spacer(1, 12)]

    normalized_rows = []
    for row in rows:
        normalized_rows.append([
            Paragraph(str(cell), body_style) if cell is not None else Paragraph("", body_style)
            for cell in row
        ])

    normalized_headers = [Paragraph(str(header), body_style) for header in headers]
    table_data = [normalized_headers] + normalized_rows

    page_width = page[0] - 18 - 18
    col_widths = [
        page_width * 0.18,
        page_width * 0.16,
        page_width * 0.16,
        page_width * 0.22,
        page_width * 0.14,
        page_width * 0.14,
    ]

    table = Table(
        table_data,
        colWidths=col_widths[: len(headers)],
        repeatRows=1,
        splitByRow=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3498db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.beige]),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("WORDWRAP", (0, 0), (-1, -1), "CJK"),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles["BodyText"]))

    doc.build(story)
    return buffer.getvalue()


@router.get("/activities/pdf")
def export_activities_pdf(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can export logs"
        )
    
    # Build query
    query = _activity_query(db)
    if _table_has_column("activity_logs", "is_deleted", db):
        query = query.filter(ActivityLog.is_deleted == False)
    
    if action:
        action_filter = _normalize_activity_action_filter(action)
        query = query.filter(literal_column("action") == action_filter)

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
    
    activities = [_activity_row_to_object(row) for row in query.order_by(ActivityLog.created_at).all()]
    
    rows = []
    for activity in activities:
        user = db.query(User).filter(User.id == activity.user_id).first()
        user_name = user.full_name if user else 'Unknown'
        action_value = _display_activity_action(getattr(activity, 'action', None))

        rows.append([
            user_name,
            action_value or '',
            f"{getattr(activity, 'entity_type', None) or '-'} (ID: {activity.entity_id})",
            activity.description or '-',
            activity.created_at.strftime('%Y-%m-%d %H:%M:%S') if activity.created_at else '',
        ])

    pdf_bytes = _build_pdf_bytes(
        "Activity Logs Report",
        ["User", "Action", "Entity", "Description", "Date"],
        rows,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=activities_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )


@router.get("/audit-logs/pdf")
def export_audit_logs_pdf(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    
    # Verify admin role
    if current_user.role.value != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can export logs"
        )
    
    # Build query
    query = db.query(AuditLog).filter(AuditLog.is_deleted == False)
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    
    if start_date:
        query = query.filter(AuditLog.changed_at >= start_date)
    
    if end_date:
        end_date_end = end_date + timedelta(days=1)
        query = query.filter(AuditLog.changed_at < end_date_end)
    
    audit_logs = query.order_by(AuditLog.changed_at).all()
    
    rows = []
    for audit in audit_logs:
        user = db.query(User).filter(User.id == audit.changed_by).first()
        user_name = user.full_name if user else 'Unknown'

        rows.append([
            f"{audit.entity_type} (ID: {audit.entity_id})",
            audit.field_name or '',
            audit.old_value or '-',
            audit.new_value or '-',
            user_name,
            audit.changed_at.strftime('%Y-%m-%d %H:%M:%S') if audit.changed_at else '',
        ])

    pdf_bytes = _build_pdf_bytes(
        "Audit Logs Report",
        ["Entity", "Field", "Old Value", "New Value", "Changed By", "Date"],
        rows,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        }
    )
