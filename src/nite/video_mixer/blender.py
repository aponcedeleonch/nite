from typing import List, Optional
from abc import ABC, abstractmethod
from enum import Enum
import time

import numpy as np
import cv2

from nite.logging import configure_module_logging
from nite.video_mixer.audio import AudioFormat
from nite.video_mixer import TimeRecorder

LOGGING_NAME = 'nite.blender'
logger = configure_module_logging(LOGGING_NAME)


class Blender(ABC):

    def __init__(self) -> None:
        pass

    @abstractmethod
    def audio_postprocess(self, audio_sample: np.ndarray) -> Optional[np.ndarray]:
        pass

    @abstractmethod
    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        pass


class ThresholdBlender(Blender):
    def __init__(self, threshold: float, audio_format: AudioFormat) -> None:
        super().__init__()
        self.audio_format = audio_format
        self.threshold = threshold
        logger.info(f'Loaded threshold blender. Threshold: {threshold}')

    def _calculate_rms(self, audio_sample: np.ndarray) -> float:
        audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        audio_rms = np.sqrt(np.mean(audio_sample_normalized ** 2))
        return audio_rms

    def audio_postprocess(self, audio_sample: np.ndarray) -> Optional[np.ndarray]:
        audio_rms = self._calculate_rms(audio_sample)
        logger.debug(f'RMS: {audio_rms}. Audio sample: {audio_sample}.')
        if audio_rms > self.threshold:
            return audio_sample[:1]
        return None

    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        if audio_sample is None:
            return frames[0]
        return frames[1]


class MathOperation(str, Enum):
    sum = 'sum'
    substract = 'substract'
    multiply = 'multiply'
    divide = 'divide'


class MathBlender(Blender):

    def __init__(self, math_operation: MathOperation) -> None:
        super().__init__()
        self.math_operation = math_operation
        logger.info(f'Loaded math blender with operation: {math_operation}')

    def audio_postprocess(self, audio_sample: np.ndarray) -> Optional[np.ndarray]:
        return None

    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        if self.math_operation == MathOperation.sum:
            return cv2.add(frames[0], frames[1])
        elif self.math_operation == MathOperation.substract:
            return cv2.subtract(frames[0], frames[1])
        elif self.math_operation == MathOperation.multiply:
            return cv2.multiply(frames[0], frames[1])
        elif self.math_operation == MathOperation.divide:
            return cv2.divide(frames[0], frames[1])


class TimeCycledMathBlender(Blender):

    def __init__(self, cycle_time_sec: int) -> None:
        super().__init__()
        self.time_recorder = TimeRecorder(start_time=time.time(), period_timeout=cycle_time_sec)
        self.math_operations = [MathOperation.sum, MathOperation.substract, MathOperation.multiply, MathOperation.divide]
        self.current_idx = 0
        self.current_blend = MathBlender(math_operation=self.math_operations[self.current_idx])

    def audio_postprocess(self, audio_sample: np.ndarray) -> Optional[np.ndarray]:
        return None

    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        frame = self.current_blend.blend(audio_sample, frames)
        if self.time_recorder.has_period_passed:
            self.current_idx = (self.current_idx + 1) % len(self.math_operations)
            self.current_blend = MathBlender(math_operation=self.math_operations[self.current_idx])
            logger.info(f'Changed math operation to: {self.math_operations[self.current_idx]}')
        return frame


if __name__ == '__main__':
    frames = [
        '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/bunny_video-nite_video/frame00000.png',
        '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/can_video-nite_video/frame00000.png'
    ]
    frames_orig = [cv2.imread(frame) for frame in frames]
    frames = [cv2.resize(frame, (640, 480)) for frame in frames_orig]
    blender = MathBlender(math_operation='divide')
    output_frame = blender.blend(None, frames)
    cv2.imshow('output_frame', output_frame)
    cv2.waitKey(5)
    cv2.destroyAllWindows()
