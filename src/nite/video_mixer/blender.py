from typing import List, Optional
from abc import ABC, abstractmethod

import numpy as np
import cv2

from nite.logging import configure_module_logging
from nite.video_mixer.audio import AudioFormat

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
