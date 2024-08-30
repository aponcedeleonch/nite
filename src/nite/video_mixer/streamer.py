import time
from typing import List
from multiprocessing import Process, Queue

import cv2
from pydantic import BaseModel

from nite.config import TERMINATE_MESSAGE
from nite.video_mixer import ProcessWithQueue
from nite.video_mixer.video import Video
from nite.video_mixer.video_io import VideoReader
from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.streamer'
logger = configure_module_logging(LOGGING_NAME)


class VideoStream(BaseModel):
    width: int
    height: int


class VideoStreamer:
    def __init__(self, video: Video):
        self.video = video
        self.ms_to_wait = self._calculate_ms_between_frames()
        logger.info(f"Loaded streamer. Video: {self.video.metadata.name}. ms to wait between frames: {self.ms_to_wait}")

    def _calculate_ms_between_frames(self):
        ms_to_wait = int(1000 / self.video.metadata.fps)
        return ms_to_wait

    def stream(self):
        for frame in self.video.circular_frame_generator():
            cv2.imshow("frame", frame)
            cv2.waitKey(self.ms_to_wait)


class VideoCombiner(ProcessWithQueue):

    def __init__(self, videos: List[Video], video_stream: VideoStream, queue: Queue):
        super().__init__(queue=queue, sender_name='video_combiner')
        self.videos = videos
        self.video_stream = video_stream
        self.ms_to_wait = self._calculate_ms_between_frames()
        self._resize_videos()
        string_videos = ", ".join([
                                    f'Video {i_vid + 1}: {video.metadata.name}. FPS: {video.metadata.fps}'
                                    for i_vid, video in enumerate(self.videos)
                                ])
        logger.info(
                f"Loaded combiner. {string_videos}. "
                f"Output resolution: {self.video_stream}. Number of videos: {len(self.videos)}. "
                f"ms to wait between frames: {self.ms_to_wait}"
            )

    def _calculate_ms_between_frames(self):
        sum_fps = sum([video.metadata.fps for video in self.videos])
        average_fps = sum_fps / len(self.videos)
        ms_to_wait = int(1000 / average_fps)
        return ms_to_wait

    def _resize_videos(self):
        for video in self.videos:
            video.resize_frames(self.video_stream.width, self.video_stream.height)

    def stream(self):
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        for frames in zip(*generators):
            message = self.receive_message()
            if self.should_terminate(message):
                break

            if self.time_recorder.should_send_keepalive:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

            frame = frames[0]
            cv2.imshow("frame combined", frame)
            cv2.waitKey(self.ms_to_wait)
        logger.info("Stream stopped")
        cv2.destroyAllWindows()


def main():
    queue = Queue()

    input_frames1 = '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/bunny_video-nite_video'
    input_frames2 = '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/can_video-nite_video'
    video1 = VideoReader().from_frames(input_frames1)
    video2 = VideoReader().from_frames(input_frames2)

    video_stream = VideoStream(width=640, height=480)
    combiner = VideoCombiner([video1, video2], video_stream, queue=queue)
    stream_process = Process(target=combiner.stream)
    stream_process.start()

    time.sleep(10)
    terminate_msg = f'{{ "sender": "main", "receiver": "video_combiner", "message": "{TERMINATE_MESSAGE}" }}'
    queue.put(terminate_msg)
    stream_process.join()


if __name__ == "__main__":
    main()
