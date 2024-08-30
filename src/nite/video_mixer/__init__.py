import time
from datetime import timedelta
import json
from multiprocessing import Queue
from queue import Empty as QueueEmpty

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
    sender: str
    receiver: str
    message: str


class ProcessWithQueue:

    def __init__(self, queue: Queue, sender_name: str) -> None:
        self.queue = queue
        self.time_recorder = TimeRecorder(start_time=time.time())
        self.sender_name = sender_name

    def _receive_from_queue(self) -> Message:
        try:
            variable = self.queue.get(block=False)
            return variable
        except QueueEmpty:
            pass

    def send_message(self, message: str, receiver_name: str) -> None:
        message_obj = Message(sender=self.sender_name, receiver=receiver_name, message=message)
        self.queue.put(message_obj.model_dump())

    def receive_message(self) -> str:
        received_message_str = self._receive_from_queue()
        if not received_message_str:
            return
        received_message = json.loads(received_message_str)
        message_obj = Message(**received_message)
        if message_obj.receiver == self.sender_name:
            return message_obj.message

    def should_terminate(self, message: str) -> bool:
        if message and message == TERMINATE_MESSAGE:
            return True
        return False
