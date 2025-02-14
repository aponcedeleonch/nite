from datetime import datetime
from typing import Optional, Self

from pydantic import BaseModel, model_validator

from nite.audio.audio_action import BPMActionFrequency
from nite.audio.audio_processing import ChromaIndex
from nite.video_mixer.blender import BlendModes


class Segment(BaseModel):
    id: str
    video_1: str
    video_2: str
    alpha: str
    bpm_frequency: Optional[BPMActionFrequency]
    min_pitch: Optional[ChromaIndex]
    max_pitch: Optional[ChromaIndex]
    blend_operation: BlendModes
    blend_falloff: float
    updated_at: datetime
    created_at: datetime

    @model_validator(mode="after")
    def check_any_action(self) -> Self:
        if not self.bpm_frequency and not self.min_pitch and not self.max_pitch:
            raise ValueError("bpm_frequency, min_pitch, max_pitch cannot be null at the same time")
        return self


class Presentation(BaseModel):
    id: str
    width: int
    height: int
    updated_at: datetime
    created_at: datetime


class PresentationSegment(BaseModel):
    segment_id: str
    presentation_id: str
    created_at: datetime
