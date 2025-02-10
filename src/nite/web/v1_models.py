from pydantic import BaseModel


class VideoMixerSegment(BaseModel):
    video_1: str
    video_2: str
    alpha: str
    bpm_frequency: str
    min_pitch: str
    max_pitch: str
    blend_operation: str
    blend_falloff: int
