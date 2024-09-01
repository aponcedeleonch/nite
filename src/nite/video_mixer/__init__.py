import time
from typing import Optional, Union, Tuple, List
from enum import Enum
from datetime import timedelta
from multiprocessing import Queue
from queue import Empty as QueueEmpty
from dataclasses import dataclass

from pydantic import BaseModel, computed_field, field_validator
from pydantic_core.core_schema import FieldValidationInfo
import numpy as np

from nite.config import TERMINATE_MESSAGE, KEEPALIVE_TIMEOUT
from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.video_mixer'
logger = configure_module_logging(LOGGING_NAME)


class TimeRecorder(BaseModel):
    start_time: float
    last_logged_seconds: int = 0

    @computed_field
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    @computed_field
    @property
    def elapsed_seconds(self) -> int:
        return int(self.elapsed_time)

    @computed_field
    @property
    def elapsed_time_str(self) -> str:
        return timedelta(seconds=self.elapsed_time)

    @computed_field
    @property
    def should_send_keepalive(self) -> bool:
        if self.elapsed_seconds % KEEPALIVE_TIMEOUT == 0 and self.elapsed_seconds != self.last_logged_seconds:
            self.last_logged_seconds = self.elapsed_seconds
            return True
        return False


class MessageConentType(str, Enum):
    message = 'message'
    audio_sample = 'audio_sample'


class Message(BaseModel):
    content_type: MessageConentType
    content: Union[str, List[float]]

    @field_validator('content')
    def content_respects_type(cls, content, info: FieldValidationInfo):
        if 'content_type' not in info.data:
            raise ValueError('Message content_type must be defined')

        if info.data['content_type'] == MessageConentType.message and not isinstance(content, str):
            raise ValueError('Message content must be a string as content_type is message')

        if info.data['content_type'] == MessageConentType.audio_sample:
            try:
                content_npy = np.array(content)
            except Exception:
                raise ValueError('Message content must be transformable to a numpy array as content_type is audio_sample')

            if not np.issubdtype(content_npy.dtype, np.number):
                raise ValueError('Message content must be a float array as content_type is audio_sample')

        return content


@dataclass
class CommQueues:
    in_queue: Queue
    out_queue: Queue


class ProcessWithQueue:

    def __init__(self, queues: CommQueues) -> None:
        self.queues = queues
        self.time_recorder = TimeRecorder(start_time=time.time())

    def _receive_from_queue(self) -> Optional[Message]:
        try:
            message = self.queues.in_queue.get(block=False)
            return message
        except QueueEmpty:
            pass
        return None

    def send_message(self, message: str) -> None:
        message_obj = Message(content_type='message', content=message)
        self.queues.out_queue.put(message_obj)

    def send_audio_sample(self, audio_sample: np.ndarray) -> None:
        message_obj = Message(content_type='audio_sample', content=audio_sample.tolist())
        self.queues.out_queue.put(message_obj)

    def receive(self) -> Tuple[bool, Optional[np.ndarray]]:
        message_obj = self._receive_from_queue()
        if not message_obj:
            return False, None

        if message_obj.content_type == MessageConentType.audio_sample:
            return False, np.array(message_obj.content)

        if message_obj.content_type == MessageConentType.message:
            return self.should_terminate(message_obj.content), None

    def should_terminate(self, message: str) -> bool:
        if message == TERMINATE_MESSAGE:
            return True
        return False
