from typing import Optional
import time
from pathlib import Path
from datetime import timedelta
import json

import cv2

from nite.video_mixer.video import Video, VideoMetadata
from nite.config import METADATA_FILENAME, SUFFIX_NITE_VIDEO_FOLDER
from nite.logging import configure_module_logging


LOGGING_NAME = 'nite.video_io'
logger = configure_module_logging(LOGGING_NAME)


def calculate_zero_padding(num_frames: float) -> int:
    num_frames_int = int(num_frames) if int(num_frames) == num_frames else int(num_frames) + 1
    return len(str(num_frames_int))


class VideoReader:

    def _read_metadata_from_video(self, input_video: str) -> VideoMetadata:
        video_capture = cv2.VideoCapture(input_video)
        num_frames = video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = video_capture.get(cv2.CAP_PROP_FPS)
        width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        name = Path(input_video).stem
        extension = Path(input_video).suffix
        video_capture.release()
        metadata = VideoMetadata(name=name, num_frames=num_frames, fps=fps, width=width, height=height, extension=extension)
        logger.info(f'Metadata read from video {input_video}.')
        return metadata

    def _read_metadata_from_json(self, input_frames_dir: str) -> VideoMetadata:
        metadata_file = Path(input_frames_dir) / METADATA_FILENAME
        if not metadata_file.is_file():
            raise FileNotFoundError(f'Metadata file not found at {metadata_file}')

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        metadata = VideoMetadata(**metadata)
        logger.info(f'Metadata read from JSON {metadata.name}. Metadata: {metadata}')
        return metadata

    def from_video(self, input_video: str) -> Video:
        start_time = time.time()
        metadata = self._read_metadata_from_video(input_video)
        video_capture = cv2.VideoCapture(input_video)
        frame_count = 0
        frames = []
        while video_capture.isOpened() and frame_count < metadata.num_frames:
            # Extract the frame
            ret, frame = video_capture.read()
            if not ret:
                continue
            frames.append(frame)
            frame_count += 1

        video_capture.release()
        elapsed_time = time.time() - start_time
        logger.info(f'Video {metadata.name} converted to frames in {timedelta(seconds=elapsed_time)} seconds')
        return Video(metadata=metadata, frames=frames)

    def from_frames(self, input_frames_dir: str) -> Video:
        image_frames_dir = Path(input_frames_dir)
        if not image_frames_dir.is_dir():
            raise FileNotFoundError(f'Input frames directory not found at {input_frames_dir}')

        metadata = self._read_metadata_from_json(input_frames_dir)
        num_zeros_padded = calculate_zero_padding(metadata.num_frames)
        frames_paths = sorted(image_frames_dir.glob('*.png'), key=lambda x: int(x.stem[num_zeros_padded:]))
        frames = [cv2.imread(str(frame_path)) for frame_path in frames_paths]
        logger.info(f'Frames of {metadata.name} read from {input_frames_dir}')
        return Video(metadata=metadata, frames=frames)


class VideoWriter:

    def __init__(self, video: Video, output_base_dir: Optional[str] = None) -> None:
        self.video = video
        if not output_base_dir:
            output_base_dir_path = Path('.')
        else:
            output_base_dir_path = Path(output_base_dir)

        self.output_dir = output_base_dir_path / f'{self.video.metadata.name}-{SUFFIX_NITE_VIDEO_FOLDER}'
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def _write_metadata_to_json(self) -> None:
        metadata_file = self.output_dir / METADATA_FILENAME
        with open(metadata_file, 'w') as file:
            file.write(self.video.metadata.model_dump_json())
        logger.info(f'Metadata of video {self.video.metadata.name} written to {metadata_file}')

    def to_video(self) -> None:
        # Force mp4 extension
        # codecs: https://softron.zendesk.com/hc/en-us/articles/207695697-List-of-FourCC-codes-for-video-codecs
        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        output_video = self.output_dir / f'{self.video.metadata.name}_reconstructed.mp4'

        self._write_metadata_to_json()

        video_dims = (self.video.metadata.width, self.video.metadata.height)
        video_writer = cv2.VideoWriter(str(output_video), fourcc, self.video.metadata.fps, video_dims)
        for frame in self.video.frames:
            video_writer.write(frame)
        video_writer.release()
        logger.info(f'Video {self.video.metadata.name} file: {output_video} written')

    def to_frames(self) -> None:
        self._write_metadata_to_json()
        num_zeros_padded = calculate_zero_padding(self.video.metadata.num_frames)
        for i_frame, frame in enumerate(self.video.frames):
            out_frame = self.output_dir / f'frame{i_frame:0{num_zeros_padded}}.png'
            cv2.imwrite(str(out_frame), frame)

        logger.info(f'Frames of {self.video.metadata.name} written to {self.output_dir}')


if __name__ == "__main__":
    input_loc = '/Users/aponcedeleonch/Personal/bunny_video.mp4'
    video = VideoReader().from_video(input_loc)
    video_writer = VideoWriter(video, output_base_dir='/Users/aponcedeleonch/Personal/nite/src/nite/video')
    video_writer.to_frames()

    # input_frames = '/Users/aponcedeleonch/Personal/nite/src/nite/video/bunny_video-nite_video'
    # video = VideoReader().from_frames(input_frames)
    # video_writer = VideoWriter(video, output_base_dir='/Users/aponcedeleonch/Personal/nite/src/nite/video')
    # video_writer.to_video()
