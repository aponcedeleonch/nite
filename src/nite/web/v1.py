import json

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute

from nite.web import v1_models

app = FastAPI()


@app.get("/api/health")
async def health_endpoint():
    return {"status": "healthy"}


def use_name(route: APIRoute):
    return f"v1_{route.name}"


v1 = APIRouter(prefix="/api/v1")


@v1.post("/video_mixer/segment")
async def create_segment(video_mixer_segment: v1_models.VideoMixerSegment):
    return video_mixer_segment


app.include_router(v1, tags=["Nite VideoMixer API"])


def generate_openapi():
    # Generate OpenAPI JSON
    openapi_schema = app.openapi()

    # Convert the schema to JSON string for easier handling or storage
    openapi_json = json.dumps(openapi_schema, indent=2)
    print(openapi_json)
