"""Add pipeline logs

Revision ID: 20210923
Revises: 20210921
Create Date: 2021-09-23 14:16:40.052234

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20210923'
down_revision = '20210921'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('pipeline_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('jobid', sa.Integer(), nullable=False),
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('func_name', sa.String(length=80), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_logs_jobid'), 'pipeline_logs', ['jobid'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_pipeline_logs_jobid'), table_name='pipeline_logs')
    op.drop_table('pipeline_logs')
    # ### end Alembic commands ###