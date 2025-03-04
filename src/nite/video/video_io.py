import json
import time
from datetime import timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

import cv2
from pydantic import BaseModel

from nite.config import METADATA_FILENAME, SUFFIX_NITE_VIDEO_FOLDER, VIDEO_LOCATION
from nite.logging import configure_module_logging
from nite.video.video import VideoFramesPath, VideoMetadata

logger = configure_module_logging("nite.video_io")


class FramesNotFoundError(Exception):
    pass


class VideoReader:
    async def read_metadata_from_video(self, input_video: Path) -> VideoMetadata:
        video_capture = cv2.VideoCapture(str(input_video))
        num_frames = video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = video_capture.get(cv2.CAP_PROP_FPS)
        width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        name = Path(input_video).stem
        extension = Path(input_video).suffix
        video_capture.release()
        metadata = VideoMetadata(
            name=name,
            num_frames=num_frames,
            fps=fps,
            width=width,
            height=height,
            extension=extension,
        )
        logger.info(f"Metadata read from video {input_video}.")
        return metadata

    def _read_metadata_from_json(self, input_frames_dir: str) -> VideoMetadata:
        metadata_file = Path(input_frames_dir) / METADATA_FILENAME
        if not metadata_file.is_file():
            raise FileNotFoundError(f"Metadata file not found at {metadata_file}")

        with open(metadata_file, "r") as f:
            metadata = json.load(f)

        metadata = VideoMetadata(**metadata)
        logger.info(f"Metadata read from JSON {metadata.name}. Metadata: {metadata}")
        return metadata

    async def from_video(
        self, input_video: Path, metadata: VideoMetadata
    ) -> AsyncIterator[cv2.typing.MatLike]:
        start_time = time.time()
        video_capture = cv2.VideoCapture(str(input_video))
        frame_count = 0
        logger.info(
            f"Converting video {metadata.name} to frames. Number of frames: {metadata.num_frames}"
        )
        while video_capture.isOpened() and frame_count < metadata.num_frames:
            # Extract the frame
            ret, frame = video_capture.read()
            if not ret:
                continue
            # We yield the frame to not keep all the frames in memory
            yield frame
            frame_count += 1
            if frame_count % 100 == 0:
                logger.info(f"Frames extracted: {frame_count}/{metadata.num_frames}")

        video_capture.release()
        elapsed_time = time.time() - start_time
        logger.info(
            f"Video {metadata.name} converted to frames in {timedelta(seconds=elapsed_time)} secs"
        )

    async def from_frames(
        self, input_frames_dir: Path, width: int, height: int, is_alpha: bool = False
    ) -> VideoFramesPath:
        base_frames_dir = Path(input_frames_dir)
        if not base_frames_dir.is_dir():
            raise FileNotFoundError(f"Input frames directory not found at {input_frames_dir}")

        image_frames_dir_resol = base_frames_dir / f"{width}x{height}"
        if is_alpha:
            image_frames_dir = image_frames_dir_resol / "alpha"
        else:
            image_frames_dir = image_frames_dir_resol

        # We have the frames in the desired resolution and with alpha channel
        if image_frames_dir.is_dir():
            metadata = self._read_metadata_from_json(str(image_frames_dir_resol))
            return VideoFramesPath(metadata=metadata, image_frames_dir=image_frames_dir)

        # We have the frames in the right resolution but are missing the alpha
        if image_frames_dir_resol.is_dir():
            metadata = self._read_metadata_from_json(str(image_frames_dir_resol))
            video_frames_paths = VideoFramesPath(
                metadata=metadata, image_frames_dir=image_frames_dir_resol
            )
            video_frames_paths.convert_to_alpha()
        # We have the frames in a different resolution
        else:
            logger.info(
                f"Frames directory for resolution {width}x{height} not found in {base_frames_dir}. "
                "Creating it."
            )
            subdirs_existent_resolution = [
                subdir for subdir in base_frames_dir.iterdir() if subdir.is_dir()
            ]
            greatest_existing_resolution = max(
                subdirs_existent_resolution, key=lambda x: int(x.stem.split("x")[0])
            )
            metadata = self._read_metadata_from_json(str(greatest_existing_resolution))
            video_frames_paths = VideoFramesPath(
                metadata=metadata, image_frames_dir=greatest_existing_resolution
            )
            video_frames_paths.resize_frames(width, height)
            # Check if we also need to convert to alpha besides resizing
            if is_alpha:
                video_frames_paths.convert_to_alpha()

        return video_frames_paths


class VideoWriter:
    def __init__(
        self, video_metadata: VideoMetadata, output_base_dir: Optional[Path] = None
    ) -> None:
        self.video_metadata = video_metadata
        if not output_base_dir:
            output_base_dir_path = Path(".")
        else:
            output_base_dir_path = Path(output_base_dir)

        video_folder = f"{self.video_metadata.name}-{SUFFIX_NITE_VIDEO_FOLDER}"
        resolution_folder = f"{self.video_metadata.width}x{self.video_metadata.height}"
        self.output_dir = output_base_dir_path / video_folder / resolution_folder
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Store the metadata in the output directory as JSON
        self.video_metadata.to_json(self.output_dir)

    # async def to_video(self) -> None:
    #     # Force mp4 extension
    #     # codecs: https://softron.zendesk.com/hc/en-us/articles/207695697-List-of-FourCC-codes-for-video-codecs
    #     fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    #     output_video = self.output_dir / f"{self.video_metadata.name}_reconstructed.mp4"

    #     self.video_metadata.to_json(self.output_dir)

    #     video_dims = (self.video_metadata.width, self.video_metadata.height)
    #     video_writer = cv2.VideoWriter(
    #         str(output_video), fourcc, self.video_metadata.fps, video_dims
    #     )
    #     for frame in self.video.frame_as_img:
    #         video_writer.write(frame)
    #     video_writer.release()
    #     logger.info(f"Video {self.video_metadata.name} file: {output_video} written")

    async def to_frames(self, frames: AsyncIterator[cv2.typing.MatLike]) -> None:
        async for i_frame, frame in frames:
            out_frame = self.output_dir / f"frame{i_frame:0{self.video_metadata.zero_padding}}.png"
            cv2.imwrite(str(out_frame), frame)
        else:
            logger.info(f"Frames of {self.video_metadata.name} written to {self.output_dir}")


class VideoStream(BaseModel):
    width: int
    height: int


class NiteVideo:
    def __init__(self, video_path: Path, video_stream: VideoStream, is_alpha: bool = False) -> None:
        self.video_path = video_path
        self.video_stream = video_stream
        self.video_frames_path: Optional[VideoFramesPath] = None
        self.is_alpha = is_alpha

    async def __call__(self) -> VideoFramesPath:
        if self.video_frames_path is None:
            self.video_frames_path = await self.load_video()
        return self.video_frames_path

    @property
    def frames_path(self) -> Path:
        output_video_path = Path(VIDEO_LOCATION)
        video_name = Path(self.video_path).stem
        return output_video_path / f"{video_name}-{SUFFIX_NITE_VIDEO_FOLDER}"

    async def _try_to_load_frames(self) -> VideoFramesPath:
        try:
            video_frames_paths = await VideoReader().from_frames(
                self.frames_path,
                self.video_stream.width,
                self.video_stream.height,
                is_alpha=self.is_alpha,
            )
            return video_frames_paths
        except FileNotFoundError:
            raise FramesNotFoundError(f"Frames not found at {self.frames_path}")

    async def _try_to_load_video(self) -> None:
        output_video_path = Path(VIDEO_LOCATION)
        video_reader = VideoReader()
        video_metadata = await video_reader.read_metadata_from_video(self.video_path)
        video_writer = VideoWriter(video_metadata=video_metadata, output_base_dir=output_video_path)
        frames = video_reader.from_video(self.video_path, video_metadata)
        await video_writer.to_frames(frames)

    async def load_video(self) -> VideoFramesPath:
        try:
            video_frames = await self._try_to_load_frames()
            return video_frames
        except FramesNotFoundError:
            logger.info(f"Frames not found at {self.frames_path}. Loading video...")

        await self._try_to_load_video()
        return await self._try_to_load_frames()
