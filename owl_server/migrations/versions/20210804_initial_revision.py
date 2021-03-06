"""Initial revision

Revision ID: 20210804
Revises:
Create Date: 2021-08-04 15:20:27.231408

"""
from os import urandom

import sqlalchemy as sa
from alembic import op
from owl_server.crypto import PBKDF2PasswordHasher

# revision identifiers, used by Alembic.
revision = "20210804"
down_revision = None
branch_labels = None
depends_on = None


def generate_temp_password(length):
    if not isinstance(length, int) or length < 8:
        raise ValueError("password must have positive length")
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(chars[c % len(chars)] for c in urandom(length))


def insert_temp_password(user):
    temp_password = generate_temp_password(12)
    hasher = PBKDF2PasswordHasher()
    salt = hasher.salt()
    password = hasher.encode(temp_password, salt)
    cmd = "INSERT INTO owl_user VALUES (1, '{}', '{}', True, True)".format(
        user, password
    )
    op.execute(cmd)
    with open("/var/run/owl/adminPassword", "w") as fh:
        fh.write(temp_password)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "container_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pipeline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("heartbeat", sa.JSON(), nullable=True),
        sa.Column("user", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("elapsed", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pipeline_definition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pdef", sa.JSON(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("extra_pip_packages", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("token", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "owl_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("password", sa.String(length=128), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    insert_temp_password("admin")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("owl_user")
    op.drop_table("token")
    op.drop_table("pipeline_definition")
    op.drop_table("pipeline")
    op.drop_table("container_image")
    # ### end Alembic commands ###
