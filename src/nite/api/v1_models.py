from datetime import datetime
from typing import List, Optional, Self
from uuid import uuid4

from pydantic import BaseModel, field_validator, model_validator

from nite.audio.audio_action import BPMActionFrequency
from nite.audio.audio_processing import ChromaIndex
from nite.db import models as db_models
from nite.video_mixer.blender import BlendModes


class SegmentCreate(BaseModel):
    id: Optional[str] = None  # Optional to allow for creation of new segments
    video_1: str
    video_2: str
    alpha: str
    bpm_frequency: Optional[BPMActionFrequency]
    min_pitch: Optional[ChromaIndex]
    max_pitch: Optional[ChromaIndex]
    blend_operation: BlendModes
    blend_falloff: float
    updated_at: Optional[datetime] = None  # Optional to allow for creation of new segments
    created_at: Optional[datetime] = None  # Optional to allow for creation of new segments

    @model_validator(mode="after")
    def _populate_fields_at_creation(self) -> Self:
        # The 3 fields below are only set when creating a new presentation
        if not self.id and not self.updated_at and not self.created_at:
            current_time = datetime.now()
            self.id = str(uuid4())
            self.updated_at = current_time
            self.created_at = current_time

        # Just to be sure also check that at least one of the 3 fields is set
        if not self.bpm_frequency and not self.min_pitch and not self.max_pitch:
            raise ValueError("bpm_frequency, min_pitch, max_pitch cannot be null at the same time")

        return self

    def to_db_model(self) -> db_models.Segment:
        return db_models.Segment(
            id=self.id,
            video_1=self.video_1,
            video_2=self.video_2,
            alpha=self.alpha,
            bpm_frequency=self.bpm_frequency,
            min_pitch=self.min_pitch,
            max_pitch=self.max_pitch,
            blend_operation=self.blend_operation,
            blend_falloff=self.blend_falloff,
            updated_at=self.updated_at,
            created_at=self.created_at,
        )


class PresentationCreate(BaseModel):
    id: Optional[str] = None  # Optional to allow for creation of new presentations
    width: int
    height: int
    updated_at: Optional[datetime] = None  # Optional to allow for creation of new presentations
    created_at: Optional[datetime] = None  # Optional to allow for creation of new presentations

    @model_validator(mode="after")
    def _populate_fields_at_creation(self) -> Self:
        # The 3 fields below are only set when creating a new presentation
        if not self.id and not self.updated_at and not self.created_at:
            current_time = datetime.now()
            self.id = str(uuid4())
            self.updated_at = current_time
            self.created_at = current_time
        return self

    def to_db_model(self) -> db_models.Presentation:
        return db_models.Presentation(
            id=self.id,
            width=self.width,
            height=self.height,
            updated_at=self.updated_at,
            created_at=self.created_at,
        )


class PresentationSegmentsCreate(BaseModel):
    segment_ids: List[str]
    created_at: Optional[datetime] = None  # Optional to allow for creation of new presentations

    @field_validator("segment_ids", mode="after")
    @classmethod
    def is_even(cls, value: List[str]) -> List[str]:
        if len(value) == 0:
            raise ValueError(f"{value} is empty")
        return value

    @model_validator(mode="after")
    def _populate_fields_at_creation(self) -> Self:
        if not self.created_at:
            self.created_at = datetime.now()
        return self
