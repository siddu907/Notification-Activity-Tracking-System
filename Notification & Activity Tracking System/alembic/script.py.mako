\n"""${message}
Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa

${upgrades if upgrades else "pass"}

${downgrades if downgrades else "pass"}
