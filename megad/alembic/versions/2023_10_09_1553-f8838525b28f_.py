""".

Revision ID: f8838525b28f
Revises: 
Create Date: 2023-10-09 15:53:28.650325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8838525b28f"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "controllers",
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("mid", sa.String(), nullable=True),
        sa.Column("config_data", sa.LargeBinary(), nullable=True),
        sa.Column("password", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("status", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_dttm", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip"),
        sa.UniqueConstraint("mid"),
    )
    op.create_table(
        "devices",
        sa.Column("controller_id", sa.Integer(), nullable=False),
        sa.Column("unique_id", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("config_data", sa.LargeBinary(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_dttm", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["controller_id"],
            ["controllers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.create_index("devices_idx", ["controller_id", "unique_id"], unique=True)
        batch_op.create_index(batch_op.f("ix_devices_controller_id"), ["controller_id"], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_devices_controller_id"))
        batch_op.drop_index("devices_idx")

    op.drop_table("devices")
    op.drop_table("controllers")
    # ### end Alembic commands ###
