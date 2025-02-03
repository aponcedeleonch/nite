import time
from datetime import timedelta
from typing import Optional

from pydantic import BaseModel, computed_field, field_validator

from nite.config import KEEPALIVE_TIMEOUT
from nite.logging import configure_module_logging

LOGGING_NAME = "nite.video_mixer"
logger = configure_module_logging(LOGGING_NAME)


class TimeRecorderError(Exception):
    pass


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
            if self.start_time is None:
                raise TimeRecorderError("TimeRecorder has not started recording time")
            self.time_from_last_asked = self.start_time
        elapsed_time = new_time_asked - self.time_from_last_asked
        self.time_from_last_asked = new_time_asked
        return elapsed_time * 1000
