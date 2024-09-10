import time
from typing import Optional, Union, Tuple, List
from enum import Enum
from datetime import timedelta
from multiprocessing import Queue
from queue import Empty as QueueEmpty
from dataclasses import dataclass

from pydantic import BaseModel, computed_field, field_validator, ValidationInfo
import numpy as np

from nite.config import TERMINATE_MESSAGE, KEEPALIVE_TIMEOUT
from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.video_mixer'
logger = configure_module_logging(LOGGING_NAME)


class TimeRecorder(BaseModel):
    start_time: Optional[float] = None
    time_from_last_timeout: Optional[float] = None
    period_timeout_sec: float = KEEPALIVE_TIMEOUT

    @field_validator('period_timeout_sec')
    @classmethod
    def period_timeout_sec_not_zero(cls, period_timeout_sec):
        if period_timeout_sec <= 0:
            raise ValueError('period_timeout_sec must be greater than 0')
        return period_timeout_sec

    def start_recording_if_not_started(self):
        if not self.start_time:
            self.start_time = time.time()
            self.time_from_last_timeout = self.start_time

    @computed_field  # type: ignore[misc]
    @property
    def elapsed_time(self) -> float:
        if self.start_time is None:
            raise ValueError('TimeRecorder has not started recording time')
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
        return f'{timedelta(seconds=self.elapsed_time)}'

    @computed_field  # type: ignore[misc]
    @property
    def has_period_passed(self) -> bool:
        time_since_last_timeout = self.elapsed_time_since_last_timeout
        if time_since_last_timeout >= self.period_timeout_sec:
            offset = time_since_last_timeout - self.period_timeout_sec
            self.time_from_last_timeout = time.time() - offset
            return True
        return False


class MessageConentType(str, Enum):
    message = 'message'
    audio_sample = 'audio_sample'


class Message(BaseModel):
    content_type: MessageConentType
    content: Union[str, List[float]]

    @field_validator('content')
    @classmethod
    def content_respects_type(cls, content, info: ValidationInfo):
        if 'content_type' not in info.data:
            raise ValueError('Message content_type must be defined')

        if info.data['content_type'] == MessageConentType.message and not isinstance(content, str):
            raise ValueError('Message content must be a string as content_type is message')

        if info.data['content_type'] == MessageConentType.audio_sample:
            try:
                content_npy = np.array(content)
            except Exception:
                raise ValueError('content_type = audio_sample: Message content must be transformable to a numpy array')

            if not np.issubdtype(content_npy.dtype, np.number):
                raise ValueError('content_type = audio_sample. Message content must be a float array')

        return content


@dataclass
class CommQueues:
    in_queue: Queue
    out_queue: Queue


class ProcessWithQueue:

    def __init__(self, queues: CommQueues) -> None:
        self.queues = queues

    def _receive_from_queue(self) -> Optional[Message]:
        try:
            message = self.queues.in_queue.get(block=False)
            return message
        except QueueEmpty:
            pass
        return None

    def send_message(self, message: str) -> None:
        message_obj = Message(content_type=MessageConentType.message, content=message)
        self.queues.out_queue.put(message_obj)

    def send_audio_sample(self, audio_sample: np.ndarray) -> None:
        message_obj = Message(content_type=MessageConentType.audio_sample, content=audio_sample.tolist())
        self.queues.out_queue.put(message_obj)

    def receive(self) -> Tuple[bool, Optional[np.ndarray]]:
        message_obj = self._receive_from_queue()
        if not message_obj:
            return False, None

        if message_obj.content_type == MessageConentType.audio_sample:
            return False, np.array(message_obj.content)

        if message_obj.content_type == MessageConentType.message:
            return self.should_terminate(str(message_obj.content)), None
        return False, None

    def should_terminate(self, message: str) -> bool:
        if message == TERMINATE_MESSAGE:
            return True
        return False
