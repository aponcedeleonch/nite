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
    name: str
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
            name=self.name,
            width=self.width,
            height=self.height,
            updated_at=self.updated_at,
            created_at=self.created_at,
        )


class SegmentTimes(BaseModel):
    segment_id: str
    from_seconds: float
    to_seconds: float


class PresentationSegmentsCreate(BaseModel):
    segments: List[SegmentTimes]
    created_at: Optional[datetime] = None  # Optional to allow for creation of new presentations

    @field_validator("segments", mode="after")
    @classmethod
    def check_segments_exist(cls, value: List[str]) -> List[str]:
        if len(value) == 0:
            raise ValueError(f"{value} is empty")
        return value

    @model_validator(mode="after")
    def _populate_fields_at_creation(self) -> Self:
        if not self.created_at:
            self.created_at = datetime.now()
        return self


class PresentationWithNumSegments(db_models.Presentation):
    num_segments: int


class SegmentWithDuration(db_models.Segment):
    from_seconds: float
    to_seconds: float


class PresentationWithSegments(db_models.Presentation):
    segments_with_duration: List[SegmentWithDuration]

    @classmethod
    async def from_db_model(
        cls, presentation_with_segments: List[db_models.PresentationSegmentsTimingRow]
    ) -> Self:
        segments = [
            SegmentWithDuration(
                id=row.segment_id,
                video_1=row.video_1,
                video_2=row.video_2,
                alpha=row.alpha,
                bpm_frequency=row.bpm_frequency,
                min_pitch=row.min_pitch,
                max_pitch=row.max_pitch,
                blend_operation=row.blend_operation,
                blend_falloff=row.blend_falloff,
                from_seconds=row.from_seconds,
                to_seconds=row.to_seconds,
                updated_at=row.segment_updated_at,
                created_at=row.segment_created_at,
            )
            for row in presentation_with_segments
        ]
        return cls(
            id=presentation_with_segments[0].id,
            name=presentation_with_segments[0].name,
            width=presentation_with_segments[0].width,
            height=presentation_with_segments[0].height,
            updated_at=presentation_with_segments[0].updated_at,
            created_at=presentation_with_segments[0].created_at,
            segments_with_duration=segments,
        )


class SegmentsWithPresentations(db_models.Segment):
    presentation_names: List[str]

    @classmethod
    async def from_db_model(
        cls, segments_with_presentations: List[db_models.SegmentWithPresentationsRow]
    ) -> List[Self]:
        return [
            cls(
                id=segments_with_presentations.id,
                video_1=segments_with_presentations.video_1,
                video_2=segments_with_presentations.video_2,
                alpha=segments_with_presentations.alpha,
                bpm_frequency=segments_with_presentations.bpm_frequency,
                min_pitch=segments_with_presentations.min_pitch,
                max_pitch=segments_with_presentations.max_pitch,
                blend_operation=segments_with_presentations.blend_operation,
                blend_falloff=segments_with_presentations.blend_falloff,
                updated_at=segments_with_presentations.updated_at,
                created_at=segments_with_presentations.created_at,
                presentation_names=segments_with_presentations.presentation_names_list,
            )
            for segments_with_presentations in segments_with_presentations
        ]
