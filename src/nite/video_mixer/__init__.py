import time
from datetime import timedelta
from enum import Enum
from multiprocessing import Queue
from queue import Empty as QueueEmpty
from typing import List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, ValidationInfo, computed_field, field_validator

from nite.config import KEEPALIVE_TIMEOUT, TERMINATE_MESSAGE
from nite.logging import configure_module_logging

LOGGING_NAME = "nite.video_mixer"
logger = configure_module_logging(LOGGING_NAME)


class TimeRecorder(BaseModel):
    start_time: Optional[float] = None
    time_from_last_timeout: Optional[float] = None
    period_timeout_sec: float = KEEPALIVE_TIMEOUT
    time_from_last_asked: Optional[float] = None

    @field_validator("period_timeout_sec")
    @classmethod
    def period_timeout_sec_not_zero(cls, period_timeout_sec):
        if period_timeout_sec <= 0:
            raise ValueError("period_timeout_sec must be greater than 0")
        return period_timeout_sec

    def start_recording_if_not_started(self):
        if not self.start_time:
            self.start_time = time.time()
            self.time_from_last_timeout = self.start_time

    @computed_field  # type: ignore[misc]
    @property
    def elapsed_time(self) -> float:
        if self.start_time is None:
            raise ValueError("TimeRecorder has not started recording time")
        return time.time() - self.start_time

    @computed_field  # type: ignore[misc]
    @property
    def elapsed_time_since_last_timeout(self) -> float:
        if self.time_from_last_timeout is None:
            self.time_from_last_timeout = time.time()
        return time.time() - self.time_from_last_timeout

    @computed_field  # type: ignore[misc]
    @property
    def elapsed_time_str(self) -> str:
        return f"{timedelta(seconds=self.elapsed_time)}"

    @computed_field  # type: ignore[misc]
    @property
    def has_period_passed(self) -> bool:
        time_since_last_timeout = self.elapsed_time_since_last_timeout
        if time_since_last_timeout >= self.period_timeout_sec:
            offset = time_since_last_timeout - self.period_timeout_sec
            self.time_from_last_timeout = time.time() - offset
            return True
        return False

    @computed_field  # type: ignore[misc]
    @property
    def elapsed_time_in_ms_since_last_asked(self) -> float:
        new_time_asked = time.time()
        if self.time_from_last_asked is None:
            self.time_from_last_asked = self.start_time
        elapsed_time = new_time_asked - self.time_from_last_asked
        self.time_from_last_asked = new_time_asked
        return elapsed_time * 1000


class MessageConentType(str, Enum):
    message = "message"
    audio_sample = "audio_sample"
    blend_strength = "blend_strength"


class Message(BaseModel):
    content_type: MessageConentType
    content: Union[str, List[float], float]

    @field_validator("content")
    @classmethod
    def content_respects_type(cls, content, info: ValidationInfo):
        if "content_type" not in info.data:
            raise ValueError("Message content_type must be defined")

        if info.data["content_type"] == MessageConentType.message and not isinstance(content, str):
            raise ValueError("Message content must be a string as content_type is message")

        if info.data["content_type"] == MessageConentType.audio_sample:
            try:
                content_npy = np.array(content)
            except Exception:
                raise ValueError(
                    "content_type = audio_sample: Content must be transformable to a numpy array"
                )

            if not np.issubdtype(content_npy.dtype, np.number):
                raise ValueError("content_type = audio_sample. Content must be a float array")

        if info.data["content_type"] == MessageConentType.blend_strength and not isinstance(
            content, float
        ):
            raise ValueError("Message content must be a float as content_type is blend_strength")

        return content


class QueueHandler:
    def __init__(self, in_queue: Queue, out_queue: Queue) -> None:
        self.in_queue = in_queue
        self.out_queue = out_queue

    def _receive_from_queue(self) -> Optional[Message]:
        try:
            message = self.in_queue.get(block=False)
            return message
        except QueueEmpty:
            pass
        return None

    def send_message(self, message: str) -> None:
        message_obj = Message(content_type=MessageConentType.message, content=message)
        self.out_queue.put(message_obj)

    def send_audio_sample(self, audio_sample: np.ndarray) -> None:
        message_obj = Message(
            content_type=MessageConentType.audio_sample, content=audio_sample.tolist()
        )
        self.out_queue.put(message_obj)

    def send_blend_strength(self, blend_strength: float) -> None:
        message_obj = Message(content_type=MessageConentType.blend_strength, content=blend_strength)
        self.out_queue.put(message_obj)

    def receive_audio_sample(self) -> Tuple[bool, Optional[np.ndarray]]:
        message_obj = self._receive_from_queue()
        if not message_obj:
            return False, None

        if message_obj.content_type == MessageConentType.audio_sample:
            return False, np.array(message_obj.content)

        if message_obj.content_type == MessageConentType.message:
            return self.should_terminate(str(message_obj.content)), None

        return False, None

    def receive_blend_strength(self) -> Tuple[bool, Optional[float]]:
        message_obj = self._receive_from_queue()
        if not message_obj:
            return False, 0.0

        if message_obj.content_type == MessageConentType.blend_strength:
            return False, message_obj.content

        if message_obj.content_type == MessageConentType.message:
            return self.should_terminate(str(message_obj.content)), None

        return False, None

    def should_terminate(self, message: str) -> bool:
        if message == TERMINATE_MESSAGE:
            return True
        return False

    def cleanup(self) -> None:
        self.in_queue.close()
        self.out_queue.close()
        self.in_queue.cancel_join_thread()
        self.out_queue.cancel_join_thread()
