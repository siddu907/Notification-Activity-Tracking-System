## Mermaid diagram

```mermaid
erDiagram
    USERS ||--o{ PROJECTS : creates
    USERS ||--o{ TASKS : assigned_to
    USERS ||--o{ PROJECT_MEMBERS : joins
    USERS ||--o{ ACTIVITY_LOGS : performs
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ AUDIT_LOGS : changes
    USERS ||--|| NOTIFICATION_PREFERENCES : has

    PROJECTS ||--o{ TASKS : contains
    PROJECTS ||--o{ PROJECT_MEMBERS : contains

    PROJECT_MEMBERS }o--|| USERS : user
    PROJECT_MEMBERS }o--|| PROJECTS : project
    TASKS }o--|| PROJECTS : project
    TASKS }o--|| USERS : assignee

    USERS {
        int id PK
        string full_name
        string email
        string password
        enum role
        datetime created_at
        bool is_deleted
    }

    PROJECTS {
        int id PK
        string name
        text description
        int created_by FK
        datetime created_at
        bool is_deleted
    }

    TASKS {
        int id PK
        string title
        text description
        enum status
        enum priority
        datetime due_date
        int assigned_to FK
        int project_id FK
        bool is_deleted
    }

    PROJECT_MEMBERS {
        int id PK
        int project_id FK
        int user_id FK
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        enum action
        string entity_type
        int entity_id
        text description
        datetime created_at
        bool is_deleted
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        text message
        enum notification_type
        string entity_type
        int entity_id
        bool is_read
        datetime read_at
        datetime created_at
        bool is_deleted
    }

    AUDIT_LOGS {
        int id PK
        string entity_type
        int entity_id
        string field_name
        text old_value
        text new_value
        int changed_by FK
        datetime changed_at
        bool is_deleted
    }

    NOTIFICATION_PREFERENCES {
        int id PK
        int user_id FK
        bool task_assigned
        bool task_reassigned
        bool task_deadline_updated
        bool new_project_member
        bool project_updated
        bool task_completed
        datetime created_at
        datetime updated_at
    }