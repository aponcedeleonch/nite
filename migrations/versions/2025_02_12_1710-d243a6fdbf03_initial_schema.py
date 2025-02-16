"""initial schema

Revision ID: d243a6fdbf03
Revises:
Create Date: 2025-02-12 17:10:50.058227+00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d243a6fdbf03"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Begin transaction
    op.execute("BEGIN TRANSACTION;")

    # segments table
    op.execute(
        """
        CREATE TABLE segments (
            id TEXT PRIMARY KEY,  -- UUID stored as TEXT
            video_1 TEXT NOT NULL,
            video_2 TEXT NOT NULL,
            alpha TEXT,
            -- bpm_frequency, min_pitch, max_pitch cannot be null at the same time
            -- the validation is done in the application
            bpm_frequency INTEGER,
            min_pitch INTEGER,
            max_pitch INTEGER,
            blend_operation TEXT NOT NULL,
            blend_falloff FLOAT NOT NULL, -- seconds
            updated_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL
        );
        """
    )
    # presentations table
    op.execute(
        """
        CREATE TABLE presentations (
            id TEXT PRIMARY KEY,  -- UUID stored as TEXT
            name TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            updated_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE (name)
        );
        """
    )
    # presentations_segments table
    op.execute(
        """
        CREATE TABLE presentations_segments (
            segment_id TEXT NOT NULL,
            presentation_id TEXT NOT NULL,
            from_seconds FLOAT NOT NULL,  -- The start time of the segment in the presentation
            to_seconds FLOAT NOT NULL,   -- The end time of the segment in the presentation
            created_at DATETIME NOT NULL,
            FOREIGN KEY (segment_id) REFERENCES segments (id) ON DELETE CASCADE,
            FOREIGN KEY (presentation_id) REFERENCES presentations (id) ON DELETE CASCADE,
            PRIMARY KEY (segment_id, presentation_id)
        );
        """
    )
    # Create indexes for foreign keys
    op.execute("CREATE INDEX fk_segment_id ON presentations_segments (segment_id);")
    op.execute("CREATE INDEX fk_presentation_id ON presentations_segments (presentation_id);")

    # End transaction
    op.execute("COMMIT;")


def downgrade() -> None:
    op.execute("BEGIN TRANSACTION;")
    op.execute("DROP TABLE presentations_segments;")
    op.execute("DROP TABLE presentation;")
    op.execute("DROP TABLE segments;")
    op.execute("COMMIT;")
