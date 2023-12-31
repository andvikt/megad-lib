""".

Revision ID: a6fd63177145
Revises: 2dde7648bb3f
Create Date: 2023-10-09 16:05:21.842949

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6fd63177145"
down_revision: Union[str, None] = "2dde7648bb3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("controllers", schema=None) as batch_op:
        batch_op.drop_constraint("uix_cont_1", type_="unique")
        batch_op.drop_index("ix_controllers_mid")
        batch_op.create_index(batch_op.f("ix_controllers_mid"), ["mid"], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("controllers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_controllers_mid"))
        batch_op.create_index("ix_controllers_mid", ["mid"], unique=False)
        batch_op.create_unique_constraint("uix_cont_1", ["ip", "mid"])

    # ### end Alembic commands ###
