import itertools
from typing import List

from pydantic import BaseModel
import cv2

from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.video'
logger = configure_module_logging(LOGGING_NAME)


class VideoMetadata(BaseModel):
    name: str
    num_frames: float
    fps: float
    extension: str = 'mp4'
    width: int = 0
    height: int = 0


class Video:

    def __init__(self, metadata: VideoMetadata, frames: List[cv2.typing.MatLike]) -> None:
        self.metadata = metadata
        self.frames = frames

    def circular_frame_generator(self):
        circular_iterator = itertools.cycle(self.frames)
        while True:
            yield next(circular_iterator)

    def resize_frames(self, width: int, height: int):
        self.frames = [cv2.resize(frame, (width, height)) for frame in self.frames]
        logger.info(f"Resized frames of {self.metadata.name} to {width}x{height}.")
