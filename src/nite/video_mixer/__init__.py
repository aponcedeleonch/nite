import itertools
from typing import List
from multiprocessing import Queue
from queue import Empty as QueueEmpty

from pydantic import BaseModel, computed_field
import cv2
import pyaudio

from nite.config import TERMINATE_MESSAGE
from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.video_mixer'
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


class AudioFormat(BaseModel):
    name: str
    pyaudio_format: int
    bits_per_sample: int
    unpack_format: str

    @computed_field
    @property
    def max_value(self) -> int:
        return 2 ** self.bits_per_sample

    @computed_field
    @property
    def normalization_factor(self) -> float:
        return 1 / self.max_value


short_format = AudioFormat(name='short', pyaudio_format=pyaudio.paInt16, bits_per_sample=16, unpack_format='%dh')


class ProcessWithQueue:

    def __init__(self, queue: Queue):
        self.queue = queue

    def receive_from_queue(self):
        try:
            variable = self.queue.get(block=False)
            return variable
        except QueueEmpty:
            pass

    def should_terminate(self, message):
        if message and message == TERMINATE_MESSAGE:
            return True
        return False
