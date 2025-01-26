from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from nite.config import AUDIO_SAMPLING_RATE
from nite.logging import configure_module_logging
from nite.video_mixer import TimeRecorder

logger = configure_module_logging("nite.buffers")


class Buffer(ABC):
    @abstractmethod
    def has_enough_data(self) -> bool:
        pass

    @abstractmethod
    def reset_buffer(self) -> None:
        pass

    @abstractmethod
    def add_sample_to_buffer(self, sample: np.ndarray) -> None:
        pass

    @abstractmethod
    def remove_samples_from_buffer(self) -> None:
        pass


class TimedSampleBuffer(Buffer):
    def __init__(
        self,
        max_seconds_in_buffer: int,
        min_seconds_in_buffer: int,
        buffer_cap_per_sec: int = AUDIO_SAMPLING_RATE,
    ) -> None:
        super().__init__()
        if max_seconds_in_buffer < 1:
            raise ValueError("max_seconds_in_buffer must be greater than 0")

        if max_seconds_in_buffer < min_seconds_in_buffer:
            raise ValueError("max_seconds_in_buffer must be greater than min_seconds_in_buffer")

        if buffer_cap_per_sec < 1:
            raise ValueError("buffer_cap_per_sec must be greater than 0")

        self.max_seconds_in_buffer = max_seconds_in_buffer + 1
        self.min_seconds_in_buffer = min_seconds_in_buffer + 1
        self.timer_buffer = TimeRecorder(period_timeout_sec=1)
        self.buffer_cap_per_sec = buffer_cap_per_sec
        # Rows are samples, columns are the number of seconds in the buffer
        self.buffer = np.zeros((self.buffer_cap_per_sec, 1))
        self.num_samples_per_second = np.zeros(1, dtype=int)

    def __call__(self) -> np.ndarray:
        # To make sure we do not have more information than needed in the buffer
        self._rotate_buffers()

        self.return_buffer = np.zeros(0)
        for i_sec, samples_per_sec in enumerate(self.num_samples_per_second):
            self.return_buffer = np.append(self.return_buffer, self.buffer[:samples_per_sec, i_sec])
        return self.return_buffer

    def has_enough_data(self) -> bool:
        num_seconds_in_buffer = len(self.num_samples_per_second)
        data_in_buffer = np.sum(self.num_samples_per_second)
        return num_seconds_in_buffer >= self.min_seconds_in_buffer and data_in_buffer > 0

    def reset_buffer(self) -> None:
        self.buffer = np.zeros((self.buffer_cap_per_sec, 1))
        self.num_samples_per_second = np.zeros(1, dtype=int)

    def _add_sample_to_buffer(self, sample: np.ndarray) -> None:
        current_samples = self.num_samples_per_second[-1]
        if current_samples + len(sample) > self.buffer_cap_per_sec:
            logger.warning("Buffer capacity exceeded. Dropping samples.")
            samples_to_add = self.buffer_cap_per_sec - current_samples
            self.num_samples_per_second[-1] = self.buffer_cap_per_sec
        else:
            samples_to_add = len(sample)
            self.num_samples_per_second[-1] += samples_to_add

        self.buffer[current_samples : current_samples + samples_to_add, -1] = sample[
            :samples_to_add
        ]

    def _add_second_to_buffer(self) -> None:
        self.num_samples_per_second = np.append(self.num_samples_per_second, [0])
        self.buffer = np.append(self.buffer, np.zeros((self.buffer_cap_per_sec, 1)), axis=1)

    def _rotate_buffers(self) -> None:
        if len(self.num_samples_per_second) > self.max_seconds_in_buffer:
            self.num_samples_per_second = self.num_samples_per_second[-self.max_seconds_in_buffer :]
            self.buffer = self.buffer[:, -self.max_seconds_in_buffer :]

    def remove_samples_from_buffer(self) -> None:
        raise NotImplementedError("This method is not implemented for TimedSampleBuffer")

    def add_sample_to_buffer(self, sample: np.ndarray) -> None:
        self.timer_buffer.start_recording_if_not_started()

        if self.timer_buffer.has_period_passed:
            self._add_second_to_buffer()

        self._add_sample_to_buffer(sample)

        self._rotate_buffers()


class SampleBuffer(Buffer):
    def __init__(
        self,
        max_buffer_size: Optional[int] = None,
        min_buffer_size: int = 0,
        num_samples_remove: int = 0,
    ) -> None:
        super().__init__()
        if min_buffer_size < 0:
            raise ValueError("min_buffer_size must be equal or greater than 0")

        if max_buffer_size is not None and max_buffer_size < min_buffer_size:
            raise ValueError("max_buffer_size must be equal or greater than min_buffer_size")

        self.buffer = np.zeros(0)
        self.max_buffer_size = max_buffer_size
        self.min_buffer_size = min_buffer_size
        self.samples_to_remove = num_samples_remove

    def __call__(self) -> np.ndarray:
        return self.buffer

    def has_enough_data(self) -> bool:
        return len(self.buffer) >= self.min_buffer_size

    def reset_buffer(self) -> None:
        self.buffer = np.zeros(0)

    def _rotate_buffer(self) -> None:
        if self.max_buffer_size is not None and len(self.buffer) > self.max_buffer_size:
            self.buffer = self.buffer[-self.max_buffer_size :]

    def remove_samples_from_buffer(self) -> None:
        self.buffer = self.buffer[self.samples_to_remove :]

    def add_sample_to_buffer(self, sample: np.ndarray) -> None:
        self.buffer = np.append(self.buffer, sample, axis=0)
        self._rotate_buffer()
