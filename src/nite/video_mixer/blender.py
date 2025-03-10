from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional

import cv2
import numpy as np
import structlog

logger = structlog.get_logger("nite.blender")


class Blender(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def blend(self, frames: List[cv2.typing.MatLike], blend_strength: float) -> cv2.typing.MatLike:
        pass


# Blending modes taken from: https://youtu.be/F7_kaTP7_W4?si=voz8OVzBRz3ZO2EA
# **Note:** `pick` is not a real blending mode. It's way to always pick the 2nd video without alpha
class BlendModes(str, Enum):
    normal = "normal"
    darken = "darken"
    lighten = "lighten"
    multiply = "multiply"
    screen = "screen"
    add = "add"
    difference = "difference"
    pick = "pick"


def get_video_2_weighted(
    video_2: np.ndarray, alpha: Optional[np.ndarray], blend_strength: float
) -> np.ndarray:
    video_2_weighted = (
        video_2 if alpha is None else (255.0 * video_2 * (alpha / 255.0)).astype(np.uint8)
    )
    return (video_2_weighted * blend_strength).astype(np.uint8)


def blend_normal(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return video_2_weighted


def blend_darken(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return np.where(video_1 < video_2_weighted, video_1, video_2_weighted)


def blend_lighten(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return np.where(video_1 > video_2_weighted, video_1, video_2_weighted)


def blend_multiply(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return (video_1 * video_2_weighted / 255.0).astype(np.uint8)


def blend_screen(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return (255.0 * ((1 - video_1) * (1 - video_2_weighted))).astype(np.uint8)


def blend_add(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return np.clip(video_1 + video_2_weighted, 0, 255, dtype=np.uint8)


def blend_diff(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    video_2_weighted = get_video_2_weighted(video_2, alpha, blend_strength)
    return np.abs(video_1 - video_2_weighted, dtype=np.uint8)


def blend_pick(
    video_1: np.ndarray,
    video_2: np.ndarray,
    alpha: Optional[np.ndarray],
    blend_strength: float,
) -> np.ndarray:
    return video_2


blend_functions = {
    BlendModes.normal: blend_normal,
    BlendModes.darken: blend_darken,
    BlendModes.lighten: blend_lighten,
    BlendModes.multiply: blend_multiply,
    BlendModes.screen: blend_screen,
    BlendModes.add: blend_add,
    BlendModes.difference: blend_diff,
    BlendModes.pick: blend_pick,
}


class BlenderMath(Blender):
    def __init__(self, blend_mode: BlendModes) -> None:
        super().__init__()
        self.blend_function = blend_functions[blend_mode]
        logger.info(f"Loaded math blender with operation: {blend_mode}")

    def blend(self, frames: List[cv2.typing.MatLike], blend_strength: float) -> cv2.typing.MatLike:
        video_1, video_2, alpha = frames
        return self.blend_function(video_1, video_2, alpha, blend_strength=blend_strength)


class BlendWithSong:
    def __init__(self, blender: Blender) -> None:
        self.blender = blender

    def blend(
        self,
        frames: List[cv2.typing.MatLike],
        should_blend: bool,
        blend_strength: float,
    ) -> cv2.typing.MatLike:
        """
        The output frame will be a single frame result of blending the frames with the blender.
        """
        if should_blend:
            return self.blender.blend(frames, blend_strength)
        else:
            return frames[0]
