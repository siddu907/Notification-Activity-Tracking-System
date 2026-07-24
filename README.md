# Notification & Activity Tracking System

A comprehensive project management application built with FastAPI, SQLAlchemy that implements notifications, activity logs, and audit tracking capabilities with event-driven architecture.

## Features

### Core Features Implemented 

1. **Activity Log System** 
   - Track all user activities across the platform
   - Login/logout tracking
   - Project creation, update, deletion logging
   - Task creation, assignment, status change logging
   - Searchable and filterable activity logs
   - Date-based filtering

2. **Notification System** 
   - Notification preferences per user
   - Mark notifications as read
   - Bulk operations (mark all as read)
   - Unread count tracking

3. **Audit Trail** 
   - Complete change history tracking
   - Record old and new values for every change
   - Capture who made the change and when
   - Task status change audit (Pending → In Progress → Completed)
   - Project description updates
   - Member additions tracked
   - Deadline modifications logged

1. **Notification Preferences** 
   - Per-user granular control
   - Task assigned notifications
   - Task reassigned notifications
   - Deadline update notifications
   - New member notifications
   - Project update notifications
   - Task completion notifications
   - Member removal notifications
   - Email notification toggle

2. **Log Export** 
   - CSV export for activity logs
   - CSV export for audit logs
   - PDF export capability (with HTML fallback)
   - Date range filtering
   - Entity-type filtering
   - Action-type filtering

## API Endpoints Summary

### Authentication
- `POST /auth/signup` - Register a new user
- `POST /auth/login` - Sign in and receive a JWT token
- `GET /auth/me` - Get authenticated user details

### Notifications
- `GET /notifications` - List notifications for the current user
- `GET /notifications/unread` - List unread notifications
- `GET /notifications/preferences` - Get notification preferences
- `PUT /notifications/preferences` - Update notification preferences
- `PUT /notifications/{notification_id}/read` - Mark one notification as read
- `PUT /notifications/read-all` - Mark all notifications as read
- `DELETE /notifications/{notification_id}` - Delete one notification

### Activities & Audits
- `GET /activities` - Get all activities (admin only)
- `GET /activities/user/{user_id}` - Get activities for a specific user
- `GET /activities/project/{project_id}` - Get activities for a project
- `GET /activities/audit-logs` - Get audit logs (admin only)
- `GET /activities/audit-logs/{entity_type}/{entity_id}` - Get audit history for an entity

### Exports
- `GET /exports/activities/csv` - Export activity logs as CSV
- `GET /exports/activities/pdf` - Export activity logs as PDF
- `GET /exports/audit-logs/csv` - Export audit logs as CSV
- `GET /exports/audit-logs/pdf` - Export audit logs as PDF

## Installation
1. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Run database migrations
   ```bash
   alembic upgrade head
   ```
4. Start the application
   ```bash
   uvicorn app.main:app --reload
   ```

## Configuration

### Environment Variables
Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=sqlite:///./app.db

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

### Database Setup
- SQLite is used by default (stored in `app.db`)
- For PostgreSQL, update `DATABASE_URL` in `.env`

## Project structure
```
Notification & Activity Tracking System/
│
├── alembic.ini
├── postman_collection.json
├── README.md
├── requirements.txt
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_initial.py
│       └── 0002_add_notifications.py
│
├── app/
│   |
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   ├── utils.py
│   └── routers/
│       ├── __init__.py
│       ├── auth.py
│       ├── members.py
│       ├── projects.py
│       ├── tasks.py
│       ├── users.py
│       ├── notifications.py
│       ├── activities.py
│       └── exports.py
│
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_exports.py
    ├── test_notifications_preferences.py
    ├── test_project.py
    └── test_rbac.py
```

## Database Schema

### New Tables Added

#### ActivityLogs
```sql
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    action VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id INTEGER NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0
);
```

#### Notifications
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR,
    entity_type VARCHAR,
    entity_id INTEGER,
    is_read BOOLEAN DEFAULT 0,
    read_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0
);
```

#### AuditLogs
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY,
    entity_type VARCHAR NOT NULL,
    entity_id INTEGER NOT NULL,
    field_name VARCHAR NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_by INTEGER NOT NULL,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0
);
```

#### NotificationPreferences
```sql
CREATE TABLE notification_preferences (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    task_assigned BOOLEAN DEFAULT 1,
    task_reassigned BOOLEAN DEFAULT 1,
    task_deadline_updated BOOLEAN DEFAULT 1,
    new_project_member BOOLEAN DEFAULT 1,
    project_updated BOOLEAN DEFAULT 1,
    task_completed BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Key Features & Examples

### 1. Activity Logging

Activities are automatically logged for:
- User login
- Project creation/update/deletion
- Task creation/update/deletion
- Task assignments/reassignments
- Task status changes
- Member additions

```bash
# Get user activities
curl http://localhost:8000/activities/user/1 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by action
curl http://localhost:8000/activities/user/1?action=task_created \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. Audit Trails

Track all changes to tasks and projects:

```bash
# Get task change history
curl http://localhost:8000/activities/audit-logs/Task/5 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
[
  {
    "id": 1,
    "entity_type": "Task",
    "entity_id": 5,
    "field_name": "status",
    "old_value": "Pending",
    "new_value": "In Progress",
    "changed_by": 1,
    "changed_at": "2026-07-21T10:30:00"
  },
  {
    "id": 2,
    "entity_type": "Task",
    "entity_id": 5,
    "field_name": "status",
    "old_value": "In Progress",
    "new_value": "Completed",
    "changed_by": 1,
    "changed_at": "2026-07-21T15:45:00"
  }
]
```

### 3. Log Exports

Export logs for reporting and compliance:

```bash
# Export activity logs as CSV
curl "http://localhost:8000/exports/activities/csv?start_date=2026-01-01" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o activities_report.csv

# Export audit logs as PDF
curl "http://localhost:8000/exports/audit-logs/pdf?entity_type=Task" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o audit_report.pdf
```

## Notification Types

1. **Task Assigned** - When a task is assigned to a user
2. **Task Reassigned** - When a task is reassigned
3. **Task Deadline Updated** - When task deadline changes
4. **New Project Member Added** - When user is added to project
5. **Project Updated** - When project details change
6. **Task Completed** - When task is marked complete

## Activity Actions Tracked

1. User Login
3. Project Created
4. Project Updated
5. Project Deleted
6. Task Created
7. Task Assigned
8. Task Reassigned
9. Task Status Changed
10. Task Deleted
11. Member Added

## API Documentation

Full interactive documentation available at:
- Swagger UI: http://localhost:8000/docs

## Testing

Run tests with pytest:
```bash
pytest tests/
```

## Roles and Permissions

- **Admin**: Full access to all endpoints
- **Manager**: Can create/manage projects and tasks, add members
- **Member**: Can view assigned tasks, update task status

## Performance Features

- Pagination support on all list endpoints
- Soft deletes for data retention
- Database indexing for fast queries

## Error Handling

All endpoints return appropriate HTTP status codes:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Server Error

## Troubleshooting

### Database Errors
- Run `alembic upgrade head`
- Check database file/connection string

## Postman Collection

A Postman collection is included (`postman_collection.json`) with pre-configured requests for all endpoints.

Import in Postman:
1. Open Postman
2. Click Import
3. Select `postman_collection.json`
4. Update `BASE_URL` and `TOKEN` variables

### Login
- Endpoint: `POST /auth/login`
- Request type: form data
- Fields:
  - `username`: user email
  - `password`: user password
  - `role` (optional): user role
- Example using `curl`:
  ```bash
  curl -X POST "http://127.0.0.1:8000/auth/login" \
    -d "username=admin@example.com" \
    -d "password=strongpassword" \
    -d "role=Admin"
  ```
- Response:
  ```json
  {
    "access_token": "<TOKEN>",
    "token_type": "bearer"
  }
  ```
- Use the returned `access_token` in the `Authorization` header for all authenticated requests.

### Authenticated requests
- Use the returned token in the `Authorization` header:
  ```http
  Authorization: Bearer <TOKEN>
  ```

> Note: In the provided Postman collection, `base_url` is already set as a collection variable and the `Login` request saves `access_token` automatically. After running `Login` once, protected requests can use `Bearer {{access_token}}` without manually pasting the token each time.

## API Reference

### Projects
#### Create project
- `POST /projects`
- Roles: `Admin`, `Manager`
- Request body:
  ```json
  {
    "name": "New Project",
    "description": "Project description"
  }
  ```

#### List projects
- `GET /projects`
- Optional query parameters:
  - `search` (string)
  - `page` (int)
  - `page_size` (int)

#### Get project details
- `GET /projects/{project_id}`

#### Update project
- `PUT /projects/{project_id}`
- Roles: `Admin`, `Manager` (if project member)
- Request body:
  ```json
  {
    "name": "Updated Project",
    "description": "Updated description"
  }
  ```

#### Delete project (soft delete)
- `DELETE /projects/{project_id}`
- Roles: `Admin`

#### Project analytics
- `GET /projects/{project_id}/analytics`
- Roles: `Admin`, `Manager`, `Member` (if project member)

#### Overall analytics
- `GET /projects/analytics`
- Roles: `Admin`, `Manager`

### Project members
#### Add member
- `POST /projects/{project_id}/members`
- Roles: `Admin`, `Manager`
- Request body:
  ```json
  {
    "user_id": 2
  }
  ```

#### List members
- `GET /projects/{project_id}/members`

### Tasks
#### Create task
- `POST /tasks`
- Roles: `Admin`, `Manager`
- Request body:
  ```json
  {
    "title": "Task title",
    "description": "Task details",
    "status": "Pending",
    "priority": "High",
    "due_date": "2026-08-01T12:00:00Z",
    "assigned_to": 3,
    "project_id": 1
  }
  ```

#### List tasks
- `GET /tasks`
- Optional filters:
  - `status`
  - `priority`
  - `assigned_to`
  - `project_id`
  - `page`
  - `page_size`

#### Get task details
- `GET /tasks/{task_id}`

#### Update task
- `PUT /tasks/{task_id}`
- Members may only update `status` or `priority` for assigned tasks.
- Managers may update tasks for their projects.
- Admins may update any task.

#### Delete task (soft delete)
- `DELETE /tasks/{task_id}`
- Roles: `Admin`, `Manager`

### User management
#### List users
- `GET /users`
- Roles: `Admin`, `Manager`

#### Get user details
- `GET /users/{user_id}`
- Roles: `Admin`, `Manager`

#### Update user
- `PUT /users/{user_id}`
- Roles: `Admin`
- Request body fields are optional:
  ```json
  {
    "full_name": "Updated Name",
    "email": "new@example.com",
    "password": "newpassword",
    "role": "Manager"
  }
  ```

#### Delete user (soft delete)
- `DELETE /users/{user_id}`
- Roles: `Admin`
- Soft deletes the user so related projects/tasks remain intact

## Postman collection
- A Postman collection is available in `postman_collection.json` for testing the API endpoints.

## Testing
Run the full test suite with:
```bash
pytest -q tests
```
