from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.database import engine
from app import models
from app.routers import auth, projects, tasks, members, users, notifications, activities, exports

models.Base.metadata.create_all(bind=engine)


def _ensure_activity_log_schema():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "activity_logs" not in inspector.get_table_names():
            return

        columns = {col["name"] for col in inspector.get_columns("activity_logs")}
        required_columns = {"id", "user_id", "action", "entity_type", "entity_id", "description", "created_at", "is_deleted"}

        if required_columns.issubset(columns):
            return

        entity_type_src = "entity_type" if "entity_type" in columns else "target_type" if "target_type" in columns else "'Unknown'"
        entity_id_src = "entity_id" if "entity_id" in columns else "target_id" if "target_id" in columns else "0"
        description_src = "description" if "description" in columns else "NULL"
        is_deleted_src = "is_deleted" if "is_deleted" in columns else "0"
        created_at_src = "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP"

        conn.execute(text(
            """
            CREATE TABLE activity_logs_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id INTEGER NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT 0
            )
            """
        ))

        conn.execute(text(
            f"""
            INSERT INTO activity_logs_new (id, user_id, action, entity_type, entity_id, description, created_at, is_deleted)
            SELECT id, user_id, action, {entity_type_src}, {entity_id_src}, {description_src}, {created_at_src}, {is_deleted_src}
            FROM activity_logs
            """
        ))

        conn.execute(text("DROP TABLE activity_logs"))
        conn.execute(text("ALTER TABLE activity_logs_new RENAME TO activity_logs"))


def _ensure_notifications_schema():
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "notifications" not in inspector.get_table_names():
            return

        columns = {col["name"] for col in inspector.get_columns("notifications")}
        required_columns = {
            "id", "user_id", "title", "message", "notification_type",
            "entity_type", "entity_id", "is_read", "read_at", "created_at", "is_deleted"
        }

        if required_columns.issubset(columns):
            return

        title_src = "title" if "title" in columns else "subject" if "subject" in columns else "''"
        message_src = "message" if "message" in columns else "''"
        notification_type_src = "notification_type" if "notification_type" in columns else "NULL"
        entity_type_src = "entity_type" if "entity_type" in columns else "NULL"
        entity_id_src = "entity_id" if "entity_id" in columns else "NULL"
        is_read_src = "is_read" if "is_read" in columns else '"read"' if "read" in columns else "0"
        read_at_src = "read_at" if "read_at" in columns else "NULL"
        created_at_src = "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP"

        conn.execute(text(
            """
            CREATE TABLE notifications_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR NOT NULL,
                message TEXT NOT NULL,
                notification_type VARCHAR,
                entity_type VARCHAR,
                entity_id INTEGER,
                is_read BOOLEAN NOT NULL DEFAULT 0,
                read_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN NOT NULL DEFAULT 0
            )
            """
        ))

        conn.execute(text(
            f"""
            INSERT INTO notifications_new (
                id, user_id, title, message, notification_type,
                entity_type, entity_id, is_read, read_at, created_at, is_deleted
            )
            SELECT
                id,
                user_id,
                {title_src} AS title,
                {message_src} AS message,
                {notification_type_src} AS notification_type,
                {entity_type_src} AS entity_type,
                {entity_id_src} AS entity_id,
                {is_read_src} AS is_read,
                {read_at_src} AS read_at,
                {created_at_src} AS created_at,
                0 AS is_deleted
            FROM notifications
            """
        ))

        conn.execute(text("DROP TABLE notifications"))
        conn.execute(text("ALTER TABLE notifications_new RENAME TO notifications"))


_ensure_activity_log_schema()
_ensure_notifications_schema()

app = FastAPI(
    title="Notification & Activity Tracking System",
    description="""
## Project Management API with Notifications, Activity Logs & Audit Trails
""", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
app.include_router(members.router, prefix="/projects", tags=["Project Members"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(activities.router, prefix="/activities", tags=["Activities"])
app.include_router(activities.audit_router, prefix="/activities", tags=["Audit Logs"])
app.include_router(exports.router, prefix="/exports", tags=["Export Logs"])

