from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.database import Base

class RoleEnum(str, enum.Enum):
    admin = "Admin"
    manager = "Manager"
    member = "Member"

class StatusEnum(str, enum.Enum):
    pending = "Pending"
    in_progress = "In Progress"
    completed = "Completed"

class PriorityEnum(str, enum.Enum):
    low = "Low"
    medium = "Medium"
    high = "High"

class ActionEnum(str, enum.Enum):
    user_login = "User Login"
    user_logout = "User Logout"
    project_created = "Project Created"
    project_updated = "Project Updated"
    project_deleted = "Project Deleted"
    task_created = "Task Created"
    task_assigned = "Task Assigned"
    task_reassigned = "Task Reassigned"
    task_status_changed = "Task Status Changed"
    task_deleted = "Task Deleted"
    member_added = "Member Added"
    member_removed = "Member Removed"

class NotificationTypeEnum(str, enum.Enum):
    task_assigned = "Task Assigned"
    task_reassigned = "Task Reassigned"
    task_deadline_updated = "Task Deadline Updated"
    new_project_member = "New Project Member Added"
    project_updated = "Project Updated"
    task_completed = "Task Completed"
    project_member_removed = "Project Member Removed"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    created_projects = relationship("Project", back_populates="creator")
    assigned_tasks = relationship("Task", back_populates="assignee")
    memberships = relationship("ProjectMember", back_populates="user")
    activity_logs = relationship("ActivityLog", foreign_keys="ActivityLog.user_id")
    notifications = relationship("Notification", foreign_keys="Notification.user_id")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.changed_by")
    notification_preference = relationship("NotificationPreference", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    creator = relationship("User", back_populates="created_projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete")
    tasks = relationship("Task", back_populates="project", cascade="all, delete")

class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="memberships")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(Enum(StatusEnum), nullable=False, default=StatusEnum.pending)
    priority = Column(Enum(PriorityEnum), nullable=False, default=PriorityEnum.medium)
    due_date = Column(DateTime(timezone=True))
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)

    assignee = relationship("User", back_populates="assigned_tasks")
    project = relationship("Project", back_populates="tasks")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(Enum(ActionEnum), nullable=False)
    entity_type = Column(String, nullable=False)  # "User", "Project", "Task", "ProjectMember"
    entity_id = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    user = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(Enum(NotificationTypeEnum), nullable=True)
    entity_type = Column(String, nullable=True)  # "Task", "Project", etc.
    entity_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)  # "Task", "Project", etc.
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)

    user = relationship("User")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    task_assigned = Column(Boolean, nullable=False, default=True)
    task_reassigned = Column(Boolean, nullable=False, default=True)
    task_deadline_updated = Column(Boolean, nullable=False, default=True)
    new_project_member = Column(Boolean, nullable=False, default=True)
    project_updated = Column(Boolean, nullable=False, default=True)
    task_completed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
