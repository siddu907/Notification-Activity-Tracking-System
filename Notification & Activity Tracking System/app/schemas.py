from datetime import datetime
from typing import Optional, List
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field
from app.models import RoleEnum, StatusEnum, PriorityEnum, ActionEnum, NotificationTypeEnum

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[RoleEnum] = None

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: RoleEnum

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[RoleEnum] = None

class UserInfo(BaseModel):
    user_id: int
    full_name: str
    role: RoleEnum

    model_config = ConfigDict(from_attributes=True)

class ActivityActor(BaseModel):
    id: int
    full_name: str
    role: RoleEnum

    model_config = ConfigDict(from_attributes=True)

class UserRead(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: RoleEnum

    model_config = ConfigDict(from_attributes=True)

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    pass

class ProjectRead(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str] = None
    project_name: str
    project_description: Optional[str] = None
    created_at: datetime
    is_deleted: bool
    created_by_user: UserInfo

    model_config = ConfigDict(from_attributes=True)

class ProjectDetailRead(BaseModel):
    project_id: int
    project_name: str
    project_description: Optional[str] = None
    created_by_user: UserInfo
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProjectMemberCreate(BaseModel):
    user_id: int

class ProjectMemberRead(BaseModel):
    project_id: int
    project_name: str
    user_id: int
    full_name: str
    role: RoleEnum

    model_config = ConfigDict(from_attributes=True)

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[StatusEnum] = StatusEnum.pending
    priority: Optional[PriorityEnum] = PriorityEnum.medium
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = None
    project_id: int

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[StatusEnum] = None
    priority: Optional[PriorityEnum] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[int] = None


class TaskRead(BaseModel):
    id: int
    task_id: int
    project_id: int
    project_name: str
    title: str
    task_title: str
    description: Optional[str] = None
    task_description: Optional[str] = None
    status: StatusEnum
    priority: PriorityEnum
    due_date: Optional[datetime] = None
    assigned_to_user: Optional[UserInfo] = None
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)



class ActivityLogCreate(BaseModel):
    user_id: int
    action: ActionEnum
    entity_type: str
    entity_id: int
    description: Optional[str] = None

class ActivityLogRead(BaseModel):
    id: int
    user_id: int
    performed_by: Optional[ActivityActor] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: int
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)




class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str
    notification_type: Optional[NotificationTypeEnum] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None

class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None

class NotificationRead(BaseModel):
    id: int
    user_id: int
    title: Optional[str] = None
    message: Optional[str] = None
    notification_type: Optional[NotificationTypeEnum] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)




class AuditLogCreate(BaseModel):
    entity_type: str
    entity_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: int

class AuditLogRead(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    field_name: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: int
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)




class NotificationPreferenceUpdate(BaseModel):
    task_assigned: Optional[bool] = None
    task_reassigned: Optional[bool] = None
    task_deadline_updated: Optional[bool] = None
    new_project_member: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("new_project_member", "project_member"),
    )
    project_updated: Optional[bool] = None
    task_completed: Optional[bool] = None

    model_config = ConfigDict(populate_by_name=True)

class NotificationPreferenceRead(BaseModel):
    id: int
    user_id: int
    task_assigned: bool
    task_reassigned: bool
    task_deadline_updated: bool
    new_project_member: bool
    project_updated: bool
    task_completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

