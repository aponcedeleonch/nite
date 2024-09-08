from typing import Optional
import time
from pathlib import Path
from datetime import timedelta
import json

import cv2

from nite.video_mixer.video import VideoFramesPath, VideoMetadata, VideoFramesImg, VideoFrames
from nite.config import METADATA_FILENAME, SUFFIX_NITE_VIDEO_FOLDER
from nite.logging import configure_module_logging


LOGGING_NAME = 'nite.video_io'
logger = configure_module_logging(LOGGING_NAME)


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

    def from_video(self, input_video: str) -> VideoFramesImg:
        start_time = time.time()
        metadata = self._read_metadata_from_video(input_video)
        video_capture = cv2.VideoCapture(input_video)
        frame_count = 0
        frames_imgs = []
        while video_capture.isOpened() and frame_count < metadata.num_frames:
            # Extract the frame
            ret, frame = video_capture.read()
            if not ret:
                continue
            frames_imgs.append(frame)
            frame_count += 1

        video_capture.release()
        elapsed_time = time.time() - start_time
        logger.info(f'Video {metadata.name} converted to frames in {timedelta(seconds=elapsed_time)} seconds')
        return VideoFramesImg(metadata=metadata, frames_imgs=frames_imgs)

    def from_frames(self, input_frames_dir: str, width: int, height: int) -> VideoFramesPath:
        base_frames_dir = Path(input_frames_dir)
        if not base_frames_dir.is_dir():
            raise FileNotFoundError(f'Input frames directory not found at {input_frames_dir}')

        image_frames_dir = base_frames_dir / f'{width}x{height}'
        if image_frames_dir.is_dir():
            metadata = self._read_metadata_from_json(str(image_frames_dir))
            return VideoFramesPath(metadata=metadata, image_frames_dir=image_frames_dir)

        logger.info(f'Frames directory for resolution {width}x{height} not found in {base_frames_dir}. Creating it.')
        subdirs_existent_resolution = [subdir for subdir in base_frames_dir.iterdir() if subdir.is_dir()]
        greatest_existing_resolution = max(subdirs_existent_resolution, key=lambda x: int(x.stem.split('x')[0]))
        metadata = self._read_metadata_from_json(str(greatest_existing_resolution))
        video_frames_paths = VideoFramesPath(metadata=metadata, image_frames_dir=greatest_existing_resolution)
        video_frames_paths.resize_frames(width, height)
        return video_frames_paths


class VideoWriter:

    def __init__(self, video: VideoFrames, output_base_dir: Optional[str] = None) -> None:
        self.video = video
        if not output_base_dir:
            output_base_dir_path = Path('.')
        else:
            output_base_dir_path = Path(output_base_dir)

        video_folder = f'{self.video.metadata.name}-{SUFFIX_NITE_VIDEO_FOLDER}'
        resolution_folder = f'{self.video.metadata.width}x{self.video.metadata.height}'
        self.output_dir = output_base_dir_path / video_folder / resolution_folder
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def to_video(self) -> None:
        # Force mp4 extension
        # codecs: https://softron.zendesk.com/hc/en-us/articles/207695697-List-of-FourCC-codes-for-video-codecs
        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
        output_video = self.output_dir / f'{self.video.metadata.name}_reconstructed.mp4'

        self.video.metadata.to_json(self.output_dir)

        video_dims = (self.video.metadata.width, self.video.metadata.height)
        video_writer = cv2.VideoWriter(str(output_video), fourcc, self.video.metadata.fps, video_dims)
        for frame in self.video.frame_as_img:
            video_writer.write(frame)
        video_writer.release()
        logger.info(f'Video {self.video.metadata.name} file: {output_video} written')

    def to_frames(self) -> None:
        self.video.metadata.to_json(self.output_dir)
        for i_frame, frame in enumerate(self.video.frame_as_img):
            out_frame = self.output_dir / f'frame{i_frame:0{self.video.metadata.zero_padding}}.png'
            cv2.imwrite(str(out_frame), frame)

        logger.info(f'Frames of {self.video.metadata.name} written to {self.output_dir}')


if __name__ == "__main__":
    input_loc = '/Users/aponcedeleonch/Personal/can_video.mp4'
    video_frames_img = VideoReader().from_video(input_loc)
    video_writer = VideoWriter(video_frames_img, output_base_dir='/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer')
    video_writer.to_frames()

    input_frames = '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/can_video-nite_video'
    video_frames_paths = VideoReader().from_frames(input_frames, 640, 480)
    # video_writer = VideoWriter(video, output_base_dir='/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer')
    # video_writer.to_video()
