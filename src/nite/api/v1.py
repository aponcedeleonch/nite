import json
from uuid import UUID

from fastapi import APIRouter, FastAPI

from nite.api import v1_models
from nite.db.connection import DbReader, DbWriter

app = FastAPI()
db_writer = DbWriter()
db_reader = DbReader()


@app.get("/api/health")
async def health_endpoint():
    return {"status": "healthy"}


v1 = APIRouter(prefix="/api/v1")


@v1.post("/video_mixer/presentations")
async def create_presentation(presentation_to_create: v1_models.PresentationCreate):
    return await db_writer.create_presentation(presentation_to_create.to_db_model())


@v1.post("/video_mixer/segments")
async def create_segment(segment_to_create: v1_models.SegmentCreate):
    return await db_writer.create_segment(segment_to_create.to_db_model())


@v1.put(
    "/video_mixer/presentations/{presentation_id}/segments",
    status_code=204,
)
async def associate_presentation_segments(
    presentation_id: UUID, segments_create: v1_models.PresentationSegmentsCreate
) -> None:
    await db_writer.associate_presentation_segments(str(presentation_id), segments_create)


app.include_router(v1, tags=["Nite VideoMixer API"])


def generate_openapi():
    # Generate OpenAPI JSON
    openapi_schema = app.openapi()

    # Convert the schema to JSON string for easier handling or storage
    openapi_json = json.dumps(openapi_schema, indent=2)
    print(openapi_json)
