import itertools
from pathlib import Path
from typing import List
from abc import ABC, abstractmethod

from pydantic import BaseModel, computed_field
import cv2

from nite.config import METADATA_FILENAME
from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.video'
logger = configure_module_logging(LOGGING_NAME)


class VideoMetadata(BaseModel):
    name: str
    num_frames: float
    fps: float
    extension: str = 'mp4'
    width: int = 0
    height: int = 0

    @computed_field  # type: ignore[misc]
    @property
    def zero_padding(self) -> int:
        num_frames_int = int(self.num_frames) if int(self.num_frames) == self.num_frames else int(self.num_frames) + 1
        return len(str(num_frames_int))

    def to_json(self, output_dir: Path) -> None:
        metadata_file = output_dir / METADATA_FILENAME
        with open(metadata_file, 'w') as file:
            file.write(self.model_dump_json())
        logger.info(f'Metadata of video {self.name} written to {metadata_file}')


class VideoFrames(ABC):

    def __init__(self, metadata: VideoMetadata) -> None:
        self.metadata = metadata

    @abstractmethod
    def circular_frame_generator(self):
        pass

    def resize_frames(self, width: int, height: int) -> None:
        self.metadata.width = width
        self.metadata.height = height

    @property
    @abstractmethod
    def frame_as_img(self):
        pass


class VideoFramesImg(VideoFrames):

    def __init__(self, metadata: VideoMetadata, frames_imgs: List[cv2.typing.MatLike]) -> None:
        super().__init__(metadata)
        self.frames_imgs = frames_imgs

    def circular_frame_generator(self):
        frames_imgs_circular = itertools.cycle(self.frames_imgs)
        while True:
            yield next(frames_imgs_circular)

    def resize_frames(self, width: int, height: int) -> None:
        super().resize_frames(width, height)
        self.frames_imgs = [cv2.resize(frame, (width, height)) for frame in self.frames_imgs]

    @property
    def frame_as_img(self):
        return self.frames_imgs


class VideoFramesPath(VideoFrames):

    def __init__(self, metadata: VideoMetadata, image_frames_dir: Path) -> None:
        super().__init__(metadata)
        self.frames_paths = self.get_frame_paths_from_dir(image_frames_dir)

    def circular_frame_generator(self):
        frames_paths_circular = itertools.cycle(self.frames_paths)
        while True:
            frame_path = next(frames_paths_circular)
            yield cv2.imread(str(frame_path))

    def resize_frames(self, width: int, height: int):
        super().resize_frames(width, height)
        frames_base_path = Path(self.frames_paths[0]).parents[1]
        frames_base_path_resized = frames_base_path / f'{width}x{height}'
        if frames_base_path_resized.is_dir():
            logger.info(f'Frames directory found with resolution {width}x{height}. Not resizing.')
            self.frames_paths = self.get_frame_paths_from_dir(frames_base_path_resized)
            return

        frames_base_path_resized.mkdir(exist_ok=True, parents=True)
        new_paths = []
        for frame_path in self.frames_paths:
            frame = cv2.imread(str(frame_path))
            frame_resized = cv2.resize(frame, (width, height))
            frame_resized_path = frames_base_path_resized / frame_path.name
            new_paths.append(frame_resized_path)
            cv2.imwrite(str(frame_resized_path), frame_resized)

        self.metadata.to_json(frames_base_path_resized)
        self.frames_paths = new_paths
        logger.info(f"Resized frames of {self.metadata.name} to {width}x{height}.")

    def get_frame_paths_from_dir(self, image_frames_dir: Path) -> List[Path]:
        logger.info(f'Frames of {self.metadata.name} read from {image_frames_dir}')
        return list(sorted(image_frames_dir.glob('*.png'), key=lambda x: x.stem[self.metadata.zero_padding:]))

    @property
    def frame_as_img(self):
        return [cv2.imread(str(frame_path)) for frame_path in self.frames_paths]
