from typing import List, Optional
from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
import cv2

from nite.logging import configure_module_logging
from nite.video_mixer.audio_listener import AudioAction, AudioActionRMS

LOGGING_NAME = 'nite.blender'
logger = configure_module_logging(LOGGING_NAME)


class Blender(ABC):

    def __init__(self) -> None:
        pass

    @abstractmethod
    def blend(self, frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        pass


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

    def blend(self, frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        if self.math_operation == MathOperation.sum:
            return cv2.add(frames[0], frames[1])
        elif self.math_operation == MathOperation.substract:
            return cv2.subtract(frames[0], frames[1])
        elif self.math_operation == MathOperation.multiply:
            return cv2.multiply(frames[0], frames[1])
        elif self.math_operation == MathOperation.divide:
            return cv2.divide(frames[0], frames[1])


class BlendWithAudio(ABC):

    def __init__(self, audio_action: AudioAction) -> None:
        self.audio_action = audio_action

    def audio_postprocess(self, audio_sample: np.ndarray) -> Optional[np.ndarray]:
        return self.audio_action.process(audio_sample)

    @abstractmethod
    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        pass


class BlendWithAudioThreshold(BlendWithAudio):

    def __init__(self, audio_action: AudioActionRMS) -> None:
        super().__init__(audio_action)

    def blend(self, audio_sample: Optional[np.ndarray], frames: List[cv2.typing.MatLike]) -> cv2.typing.MatLike:
        if audio_sample is None:
            return frames[0]
        return frames[1]


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
