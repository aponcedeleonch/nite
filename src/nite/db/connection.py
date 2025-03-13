from pathlib import Path
from typing import List, Optional, Type

import structlog
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from pydantic import BaseModel
from sqlalchemy import CursorResult, TextClause, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from nite.api import v1_models
from nite.db import models as db_models

logger = structlog.get_logger("nite.db.connection")


class AlreadyExistsError(Exception):
    pass


class DbCreationError(Exception):
    pass


class DoesNotExistError(Exception):
    pass


class PresentationWithNoSegmentsError(Exception):
    pass


class NiteDbError(Exception):
    pass


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Ensures that foreign keys are enabled for the SQLite database at every connection.
    SQLite does not enforce foreign keys by default, so we need to enable them manually.
    [SQLAlchemy docs](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support)
    [SQLite docs](https://www.sqlite.org/foreignkeys.html)
    [SO](https://stackoverflow.com/questions/2614984/sqlite-sqlalchemy-how-to-enforce-foreign-keys)
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class NiteDb:
    def __init__(self, sqlite_str_path: Optional[str] = None):
        if not sqlite_str_path:
            current_dir = Path(__file__).parent
            sqlite_path = current_dir / "nite.db"
        else:
            sqlite_path = Path(sqlite_str_path)
        self._db_path = sqlite_path.absolute()

        self._async_db_engine = create_async_engine(
            url=f"sqlite+aiosqlite:///{self._db_path}",
            echo=False,
            isolation_level="AUTOCOMMIT",
        )


class DbWriter(NiteDb):
    def __init__(self, sqlite_str_path: Optional[str] = None):
        super().__init__(sqlite_str_path)

    async def _exec_upsert_pydantic_model(
        self, model: BaseModel, sql_command: TextClause
    ) -> BaseModel:
        """Execute an update or insert command for a Pydantic model."""
        async with self._async_db_engine.begin() as conn:
            result = await conn.execute(sql_command, model.model_dump())
            row = result.first()
            if row is None:
                raise DbCreationError(f"Failed to create model: {model}")

            # Get the class of the Pydantic object to create a new object
            model_class = model.__class__
            return model_class(**row._asdict())

    async def _exec_with_no_return(self, sql_command: TextClause, conditions: dict) -> None:
        """Execute a command that doesn't return anything."""
        async with self._async_db_engine.begin() as conn:
            await conn.execute(sql_command, conditions)

    async def create_presentation(
        self, presentation_db: db_models.Presentation
    ) -> db_models.Presentation:
        sql = text(
            """
            INSERT INTO presentations (
                id, name, width, height, updated_at, created_at
            )
            VALUES (
                :id, :name, :width, :height, :updated_at, :created_at
            )
            RETURNING *
            """
        )
        try:
            new_presentation = await self._exec_upsert_pydantic_model(presentation_db, sql)
            return new_presentation  # type: ignore[return-value]
        except IntegrityError as e:
            str_error = f"Failed to create presentation: {e}"
            raise AlreadyExistsError(str_error)
        except Exception as e:
            str_error = f"Failed to create presentation: {e}"
            raise NiteDbError(str_error)

    async def create_segment(self, segment_db: db_models.Segment) -> db_models.Segment:
        sql = text(
            """
            INSERT INTO segments (
                id, video_1, video_2, alpha, bpm_frequency, min_pitch, max_pitch, blend_operation,
                blend_falloff, updated_at, created_at
            )
            VALUES (
                :id, :video_1, :video_2, :alpha, :bpm_frequency, :min_pitch, :max_pitch,
                :blend_operation, :blend_falloff, :updated_at, :created_at
            )
            RETURNING *
            """
        )
        try:
            new_segment = await self._exec_upsert_pydantic_model(segment_db, sql)
            return new_segment  # type: ignore[return-value]
        except IntegrityError as e:
            str_error = f"Failed to create segment: {e}"
            raise AlreadyExistsError(str_error)

    async def associate_presentation_segments(
        self, presentation_id: str, segment_create: v1_models.PresentationSegmentsCreate
    ) -> None:
        async with self._async_db_engine.begin() as transaction:
            try:
                # First delete all the segments associated with the presentation
                sql_delete = text(
                    """
                    DELETE FROM presentations_segments
                    WHERE presentation_id = :presentation_id
                    """
                )
                await transaction.execute(sql_delete, {"presentation_id": presentation_id})

                # Then associate the new segments
                sql_insert = text(
                    """
                    INSERT INTO presentations_segments (
                        segment_id, presentation_id, from_seconds, to_seconds, created_at
                    )
                    VALUES (
                        :segment_id, :presentation_id, :from_seconds, :to_seconds, :created_at
                    )
                    """
                )

                for segment in segment_create.segments:
                    conditions = {
                        "segment_id": segment.segment_id,
                        "presentation_id": presentation_id,
                        "from_seconds": segment.from_seconds,
                        "to_seconds": segment.to_seconds,
                        "created_at": segment_create.created_at,
                    }
                    await transaction.execute(sql_insert, conditions)
            except Exception as e:
                await transaction.rollback()
                str_error = f"Failed to associate presentation segments: {e}"
                raise NiteDbError(str_error)


class DbReader(NiteDb):
    def __init__(self, sqlite_str_path: Optional[str] = None):
        super().__init__(sqlite_str_path)

    async def _dump_result_to_pydantic_model(
        self, model_type: Type[BaseModel], result: CursorResult
    ) -> List[BaseModel]:
        try:
            rows = [model_type(**row._asdict()) for row in result.fetchall() if row]
            return rows
        except Exception as e:
            str_error = f"Failed to dump to pydantic model: {model_type}. Error: {e}"
            logger.exception(str_error)
            raise NiteDbError(str_error)

    async def _exec_select_pydantic_model(
        self, model_type: Type[BaseModel], sql_command: TextClause
    ) -> List[BaseModel]:
        async with self._async_db_engine.begin() as conn:
            try:
                result = await conn.execute(sql_command)
                return await self._dump_result_to_pydantic_model(model_type, result)
            except Exception as e:
                str_error = f"Failed to select model: {model_type}. Error: {e}"
                logger.exception(str_error)
                raise NiteDbError(str_error)

    async def _exec_select_conditions_to_pydantic(
        self, model_type: Type[BaseModel], sql_command: TextClause, conditions: dict
    ) -> List[BaseModel]:
        async with self._async_db_engine.begin() as conn:
            try:
                result = await conn.execute(sql_command, conditions)
                return await self._dump_result_to_pydantic_model(model_type, result)
            except Exception as e:
                str_error = f"Failed to select model with conditions: {model_type}. Error: {e}"
                logger.exception(str_error)
                raise NiteDbError(str_error)

    async def get_presentation(self, presentation_id: str) -> db_models.Presentation:
        sql = text(
            """
            SELECT *
            FROM presentations
            WHERE id = :presentation_id
            """
        )
        conditions = {"presentation_id": presentation_id}
        presentation = await self._exec_select_conditions_to_pydantic(
            db_models.Presentation, sql, conditions
        )
        if not presentation:
            raise DoesNotExistError(f"Presentation with id {presentation_id} does not exist")
        return presentation[0]  # type: ignore[return-value]

    async def get_segment(self, segment_id: str) -> db_models.Segment:
        sql = text(
            """
            SELECT *
            FROM segments
            WHERE id = :segment_id
            """
        )
        conditions = {"segment_id": segment_id}
        segment = await self._exec_select_conditions_to_pydantic(db_models.Segment, sql, conditions)
        if not segment:
            raise DoesNotExistError(f"Segment with id {segment_id} does not exist")
        return segment[0]  # type: ignore[return-value]

    async def get_presentations_with_num_segments(
        self,
    ) -> List[v1_models.PresentationWithNumSegments]:
        sql = text(
            """
            SELECT
                p.id, p.name, p.width, p.height, p.updated_at, p.created_at,
                COUNT(ps.segment_id) as num_segments
            FROM presentations p
            LEFT JOIN presentations_segments ps ON p.id = ps.presentation_id
            GROUP BY p.id
            """
        )
        presentations_num_segment = await self._exec_select_pydantic_model(
            v1_models.PresentationWithNumSegments, sql
        )
        return presentations_num_segment  # type: ignore[return-value]

    async def get_presentation_with_segments(
        self, presentation_id: str
    ) -> List[db_models.PresentationSegmentsTimingRow]:
        sql = text(
            """
            SELECT
                p.id, p.name, p.width, p.height, p.updated_at, p.created_at,
                s.id as segment_id, s.video_1, s.video_2, s.alpha, s.bpm_frequency, s.min_pitch,
                s.max_pitch, s.blend_operation, s.blend_falloff, s.updated_at as segment_updated_at,
                s.created_at as segment_created_at, ps.from_seconds, ps.to_seconds
            FROM presentations p
            INNER JOIN presentations_segments ps ON p.id = ps.presentation_id
            INNER JOIN segments s ON ps.segment_id = s.id
            WHERE p.id = :presentation_id
            """
        )
        conditions = {"presentation_id": presentation_id}
        presentation_with_segments = await self._exec_select_conditions_to_pydantic(
            db_models.PresentationSegmentsTimingRow, sql, conditions
        )
        if not presentation_with_segments:
            raise PresentationWithNoSegmentsError(
                f"Presentation with id {presentation_id} has no segments"
            )
        return presentation_with_segments  # type: ignore[return-value]

    async def get_segments_with_presentations(self) -> List[db_models.SegmentWithPresentationsRow]:
        sql = text(
            """
            SELECT
                s.id, s.video_1, s.video_2, s.alpha, s.bpm_frequency, s.min_pitch, s.max_pitch,
                s.blend_operation, s.blend_falloff, s.updated_at, s.created_at,
                GROUP_CONCAT(p.name) as presentation_names
            FROM segments s
            LEFT JOIN presentations_segments ps ON s.id = ps.segment_id
            LEFT JOIN presentations p ON ps.presentation_id = p.id
            GROUP BY
                s.id, s.video_1, s.video_2, s.alpha, s.bpm_frequency, s.min_pitch, s.max_pitch,
                s.blend_operation, s.blend_falloff, s.updated_at, s.created_at
            """
        )
        segments_with_presentations = await self._exec_select_pydantic_model(
            db_models.SegmentWithPresentationsRow, sql
        )
        return segments_with_presentations  # type: ignore[return-value]


def init_db_sync(db_path: Optional[str] = None):
    """
    Apply the latest migration to the database. If the database does not exist, it will be created.
    """
    current_dir = Path(__file__).parent
    alembic_ini_path = current_dir.parent.parent.parent / "alembic.ini"
    alembic_cfg = AlembicConfig(alembic_ini_path)
    # Only set the db path if it's provided. Otherwise use the one in alembic.ini
    if db_path:
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("DB initialized successfully.")
