import time
from datetime import timedelta
from multiprocessing import Queue
from queue import Empty as QueueEmpty
from dataclasses import dataclass

from pydantic import BaseModel, computed_field

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


class Message(BaseModel):
    content: str


@dataclass
class CommQueues:
    in_queue: Queue
    out_queue: Queue


class ProcessWithQueue:

    def __init__(self, queues: CommQueues) -> None:
        self.queues = queues
        self.time_recorder = TimeRecorder(start_time=time.time())

    def _receive_from_queue(self) -> Message:
        try:
            variable = self.queues.in_queue.get(block=False)
            return variable
        except QueueEmpty:
            pass

    def send_message(self, message: str) -> None:
        message_obj = Message(content=message)
        self.queues.out_queue.put(message_obj.model_dump())

    def receive_message(self) -> str:
        received_message = self._receive_from_queue()
        if not received_message:
            return
        message_obj = Message(**received_message)
        return message_obj.content

    def should_terminate(self, message: str) -> bool:
        if message and message == TERMINATE_MESSAGE:
            return True
        return False
