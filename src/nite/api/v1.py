import json
from contextlib import asynccontextmanager
from typing import List
from uuid import UUID

import structlog
from fastapi import APIRouter, FastAPI, HTTPException

from nite.api import v1_models
from nite.db import connection as db_connection
from nite.db import models as db_models

logger = structlog.get_logger("nite.v1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run the database initialization
    db_connection.init_db_sync()
    yield


app = FastAPI(lifespan=lifespan)
db_writer = db_connection.DbWriter()
db_reader = db_connection.DbReader()


@app.get("/api/health")
async def health_endpoint():
    return {"status": "healthy"}


v1 = APIRouter(prefix="/api/v1")


@v1.post("/video_mixer/presentations")
async def create_presentation(
    presentation_to_create: v1_models.PresentationCreate,
) -> db_models.Presentation:
    try:
        return await db_writer.create_presentation(presentation_to_create.to_db_model())
    except db_connection.AlreadyExistsError:
        str_error = "Presentation with supplied name already exists"
        logger.error(str_error)
        raise HTTPException(status_code=409, detail=str_error)
    except db_connection.NiteDbError:
        str_error = "Error creating presentation in DB"
        logger.exception(str_error)
        raise HTTPException(status_code=500, detail=str_error)
    except Exception:
        str_error = "Error creating presentation"
        logger.exception(str_error)
        raise HTTPException(status_code=500, detail=str_error)


@v1.get("/video_mixer/presentations")
async def get_presentations() -> List[v1_models.PresentationWithNumSegments]:
    return await db_reader.get_presentations_with_num_segments()


@v1.get("/video_mixer/presentations/{presentation_id}")
async def get_presentation_by_id(presentation_id: UUID) -> v1_models.PresentationWithSegments:
    try:
        await db_reader.get_presentation(str(presentation_id))
    except db_connection.DoesNotExistError:
        str_error = "Presentation with supplied ID does not exist"
        logger.error(str_error)
        raise HTTPException(status_code=404, detail=str_error)

    try:
        presentation_with_segmnets = await db_reader.get_presentation_with_segments(
            str(presentation_id)
        )
        return await v1_models.PresentationWithSegments.from_db_model(presentation_with_segmnets)
    except db_connection.PresentationWithNoSegmentsError:
        str_error = "Presentation with ID has no segments"
        logger.error(str_error)
        raise HTTPException(status_code=404, detail=str_error)
    except Exception:
        str_error = "Error retrieving presentation:"
        logger.exception(str_error)
        raise HTTPException(status_code=500, detail=str_error)


@v1.post("/video_mixer/segments")
async def create_segment(segment_to_create: v1_models.SegmentCreate) -> db_models.Segment:
    try:
        return await db_writer.create_segment(segment_to_create.to_db_model())
    except db_connection.AlreadyExistsError:
        str_error = "Segment with ID already exists"
        logger.error(str_error)
        raise HTTPException(status_code=409, detail=str_error)


@v1.get("/video_mixer/segments")
async def get_segments() -> List[v1_models.SegmentsWithPresentations]:
    segments = await db_reader.get_segments_with_presentations()
    return await v1_models.SegmentsWithPresentations.from_db_model(segments)


@v1.put(
    "/video_mixer/presentations/{presentation_id}/segments",
    status_code=204,
)
async def associate_presentation_segments(
    presentation_id: UUID, segments_create: v1_models.PresentationSegmentsCreate
) -> None:
    try:
        await db_reader.get_presentation(str(presentation_id))
    except db_connection.DoesNotExistError:
        str_error = f"Presentation with ID {presentation_id} does not exist"
        logger.error(str_error)
        raise HTTPException(status_code=404, detail=str_error)

    for segment in segments_create.segments:
        try:
            await db_reader.get_segment(str(segment.segment_id))
        except db_connection.DoesNotExistError:
            str_error = f"Segment with ID: {segment.segment_id} does not exist"
            logger.error(str_error)
            raise HTTPException(status_code=404, detail=str_error)

    try:
        await db_writer.associate_presentation_segments(str(presentation_id), segments_create)
    except db_connection.NiteDbError:
        str_error = f"Error associating segments with presentation: {presentation_id}"
        logger.exception(str_error)
        raise HTTPException(status_code=500, detail=str_error)


app.include_router(v1, tags=["Nite VideoMixer API"])


def generate_openapi():
    # Generate OpenAPI JSON
    openapi_schema = app.openapi()

    # Convert the schema to JSON string for easier handling or storage
    openapi_json = json.dumps(openapi_schema, indent=2)
    print(openapi_json)
