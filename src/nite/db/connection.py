from pathlib import Path
from typing import List, Optional, Type

from pydantic import BaseModel
from sqlalchemy import CursorResult, TextClause, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine

from nite.api import v1_models
from nite.db import models as db_models
from nite.logging import configure_module_logging

logger = configure_module_logging("nite.audio_processing")


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
    def __init__(self, sqlite_path: Optional[str] = None):
        if not sqlite_path:
            current_dir = Path(__file__).parent
            sqlite_path = current_dir / "nite.db"
        self._db_path = Path(sqlite_path).absolute()

        engine_dict = {
            "url": f"sqlite+aiosqlite:///{self._db_path}",
            "echo": False,  # Set to False in production
            "isolation_level": "AUTOCOMMIT",  # Required for SQLite
        }
        self._async_db_engine = create_async_engine(**engine_dict)


class DbWriter(NiteDb):
    def __init__(self, sqlite_path: Optional[str] = None):
        super().__init__(sqlite_path)

    async def _exec_upsert_pydantic_model(
        self, model: BaseModel, sql_command: TextClause
    ) -> Optional[BaseModel]:
        """Execute an update or insert command for a Pydantic model."""
        try:
            async with self._async_db_engine.begin() as conn:
                result = await conn.execute(sql_command, model.model_dump())
                row = result.first()
                if row is None:
                    return None

                # Get the class of the Pydantic object to create a new object
                model_class = model.__class__
                return model_class(**row._asdict())
        except Exception as e:
            str_error = f"Failed to create/update model: {model}. Error: {e}"
            logger.exception(str_error)
            raise NiteDbError(str_error)

    async def _exec_with_no_return(self, sql_command: TextClause, conditions: dict):
        """Execute a command that doesn't return anything."""
        try:
            async with self._async_db_engine.begin() as conn:
                await conn.execute(sql_command, conditions)
        except Exception as e:
            str_error = f"Failed to execute command: {sql_command}. Error: {e}"
            logger.error(str_error)
            raise NiteDbError(str_error)

    async def create_presentation(self, presentation_db: db_models.Presentation) -> None:
        sql = text(
            """
            INSERT INTO presentations (
                id, width, height, updated_at, created_at
            )
            VALUES (
                :id, :width, :height, :updated_at, :created_at
            )
            RETURNING *
            """
        )
        new_presentation = await self._exec_upsert_pydantic_model(presentation_db, sql)
        return new_presentation

    async def create_segment(self, segment_db: db_models.Presentation) -> None:
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
        new_segment = await self._exec_upsert_pydantic_model(segment_db, sql)
        return new_segment

    async def delete_provider_model(self, presentation_id: str) -> None:
        sql = text(
            """
            DELETE FROM presentations_segments
            WHERE presentation_id = :presentation_id
            """
        )

        conditions = {"presentation_id": presentation_id}
        await self._exec_with_no_return(sql, conditions)

    async def associate_presentation_segments(
        self, presentation_id: str, segment_create: v1_models.PresentationSegmentsCreate
    ) -> None:
        # First delete all the segments associated with the presentation
        await self.delete_provider_model(presentation_id)
        # Then associate the new segments
        sql = text(
            """
            INSERT INTO presentations_segments (segment_id, presentation_id, created_at)
            VALUES (:segment_id, :presentation_id, :created_at)
            """
        )

        for segment_id in segment_create.segment_ids:
            conditions = {
                "segment_id": segment_id,
                "presentation_id": presentation_id,
                "created_at": segment_create.created_at,
            }
            await self._exec_with_no_return(sql, conditions)


class DbReader(NiteDb):
    def __init__(self, sqlite_path: Optional[str] = None):
        super().__init__(sqlite_path)

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

    # async def get_prompts_with_output(self, workpace_id: str) -> List[GetPromptWithOutputsRow]:
    #     sql = text(
    #         """
    #         SELECT
    #             p.id, p.timestamp, p.provider, p.request, p.type,
    #             o.id as output_id,
    #             o.output,
    #             o.timestamp as output_timestamp,
    #             o.input_tokens,
    #             o.output_tokens,
    #             o.input_cost,
    #             o.output_cost
    #         FROM prompts p
    #         LEFT JOIN outputs o ON p.id = o.prompt_id
    #         WHERE p.workspace_id = :workspace_id
    #         ORDER BY o.timestamp DESC
    #         """
    #     )
    #     conditions = {"workspace_id": workpace_id}
    #     prompts = await self._exec_select_conditions_to_pydantic(
    #         GetPromptWithOutputsRow, sql, conditions, should_raise=True
    #     )
    #     return prompts
