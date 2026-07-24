# Notification & Activity Tracking System

## API Documentation

### Base URL
- `http://localhost:8000`

          or

- `http://127.0.0.1:8000/docs`

### Authentication
- `POST /auth/signup`
  - Registers a new user.
  - Body: `full_name`, `email`, `password`, `role`

- `POST /auth/login`
  - Logs in a user and returns JWT access token.
  - Form fields: `username`, `password`, `role` (optional)

- `GET /auth/me`
  - Returns the authenticated user's details.
  - Requires Bearer token.

### Projects
- `POST /projects/`
  - Creates a new project.
  - Roles: Admin, Manager
  - Body: `name`, `description`

- `GET /projects/`
  - Lists projects with pagination.
  - Optional query params: `project_id`, `search`, `page`, `page_size`
  - Roles: Admin, Manager, Member (only assigned projects)

- `GET /projects/{project_id}`
  - Gets project details.
  - Roles: Admin, Manager, Member (if project member)

- `PUT /projects/{project_id}`
  - Updates project details.
  - Roles: Admin, Manager
  - Body: `name`, `description`

- `DELETE /projects/{project_id}`
  - Soft deletes a project.
  - Roles: Admin

- `GET /projects/{project_id}/analytics`
  - Returns project analytics.
  - Roles: Admin, Manager, Member (if project member)

- `GET /projects/analytics`
  - Returns overall analytics.
  - Roles: Admin, Manager

### Project Members
- `POST /projects/{project_id}/members`
  - Adds a member to a project.
  - Roles: Admin, Manager
  - Body: `user_id`

- `GET /projects/{project_id}/members`
  - Lists project members.
  - Roles: Admin, Manager, Member (if project member)

### Tasks
- `POST /tasks/`
  - Creates a task.
  - Roles: Admin, Manager
  - Body: `title`, `description`, `status`, `priority`, `due_date`, `assigned_to`, `project_id`

- `GET /tasks/`
  - Lists tasks.
  - Optional query params: `assigned_to`, `project_id`, `page`, `page_size`
  - Roles: Admin, Manager, Member (assigned tasks only)

- `GET /tasks/{task_id}`
  - Gets a task by id.
  - Roles: Admin, Manager, Member (assigned task or project member)

- `PUT /tasks/{task_id}`
  - Updates a task.
  - Roles: Admin, Manager, Member (only status/priority if assigned)
  - Body: optional fields such as `title`, `description`, `status`, `priority`, `due_date`, `assigned_to`

- `DELETE /tasks/`
  - Soft deletes a task.
  - Roles: Admin, Manager

### Users
- `GET /users/`
  - Lists users.
  - Roles: Admin, Manager

- `GET /users/{user_id}`
  - Gets a specific user.
  - Roles: Admin, Manager

- `PUT /users/{user_id}`
  - Updates a user.
  - Roles: Admin
  - Body: optional `full_name`, `email`, `password`, `role`

- `DELETE /users/{user_id}`
  - Soft deletes a user.
  - Roles: Admin

### Notifications
- `GET /notifications`
  - Lists notifications for the current user.
  - Query params: `skip`, `limit`, `is_read`
  - Requires Bearer token.

- `GET /notifications/unread`
  - Lists unread notifications.
  - Query params: `skip`, `limit`
  - Requires Bearer token.

- `GET /notifications/preferences`
  - Gets the current user's notification preferences.
  - Requires Bearer token.

- `PUT /notifications/preferences`
  - Updates notification preferences.
  - Requires Bearer token.

- `PUT /notifications/{notification_id}/read`
  - Marks one notification as read.
  - Requires Bearer token.

- `PUT /notifications/read-all`
  - Marks all notifications as read.
  - Requires Bearer token.

- `DELETE /notifications/{notification_id}`
  - Deletes one notification.
  - Requires Bearer token.

### Activities
- `GET /activities`
  - Lists all activity logs.
  - Roles: Admin only
  - Query params: `skip`, `limit`, `action`, `entity_type`, `start_date`, `end_date`

- `GET /activities/user/{user_id}`
  - Lists activity logs for a particular user.
  - Query params: `skip`, `limit`, `action`, `entity_type`, `start_date`, `end_date`

- `GET /activities/project/{project_id}`
  - Lists activity logs for a project.
  - Query params: `skip`, `limit`, `action`, `entity_type`, `start_date`, `end_date`

### Audit Logs
- `GET /activities/audit-logs`
  - Lists all audit logs.
  - Roles: Admin only
  - Query params: `skip`, `limit`, `entity_type`, `start_date`, `end_date`

- `GET /activities/audit-logs/{entity_type}/{entity_id}`
  - Gets audit history for a specific entity.
  - Requires Bearer token.

### Export Logs
- `GET /exports/activities/csv`
  - Exports activity logs as CSV.
  - Roles: Admin only
  - Query params: `start_date`, `end_date`, `action`, `entity_type`

- `GET /exports/activities/pdf`
  - Exports activity logs as PDF.
  - Roles: Admin only
  - Query params: `start_date`, `end_date`, `action`, `entity_type`

- `GET /exports/audit-logs/csv`
  - Exports audit logs as CSV.
  - Roles: Admin only
  - Query params: `start_date`, `end_date`, `entity_type`

- `GET /exports/audit-logs/pdf`
  - Exports audit logs as PDF.
  - Roles: Admin only
  - Query params: `start_date`, `end_date`, `entity_type`

### Date format for filters
- Use `YYYY-MM-DD` for `start_date` and `end_date`
- Example: `start_date=2026-07-24`
- Example: `end_date=2026-07-24`

### Authorization
- All protected endpoints require:
  `Authorization: Bearer <access_token>`

### Interactive Docs
- Swagger UI: `http://localhost:8000/docs`

