"""adding indexes to models

Revision ID: 6fbe9cace832
Revises: f895232c144a
Create Date: 2025-01-23 11:02:59.534372

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6fbe9cace832"
down_revision: Union[str, None] = "f895232c144a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index("agent_passages_created_at_id_idx", "agent_passages", ["created_at", "id"], unique=False)
    op.create_index("ix_agents_created_at", "agents", ["created_at", "id"], unique=False)
    op.create_index("created_at_label_idx", "block", ["created_at", "label"], unique=False)
    op.create_index("ix_jobs_created_at", "jobs", ["created_at", "id"], unique=False)
    op.create_index("ix_messages_created_at", "messages", ["created_at", "id"], unique=False)
    op.create_index("source_passages_created_at_id_idx", "source_passages", ["created_at", "id"], unique=False)
    op.create_index("source_created_at_id_idx", "sources", ["created_at", "id"], unique=False)
    op.create_index("ix_tools_created_at_name", "tools", ["created_at", "name"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_tools_created_at_name", table_name="tools")
    op.drop_index("source_created_at_id_idx", table_name="sources")
    op.drop_index("source_passages_created_at_id_idx", table_name="source_passages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("created_at_label_idx", table_name="block")
    op.drop_index("ix_agents_created_at", table_name="agents")
    op.drop_index("agent_passages_created_at_id_idx", table_name="agent_passages")
    # ### end Alembic commands ###