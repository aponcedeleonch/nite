import time
from typing import List
from multiprocessing import Process, Queue

import cv2

from nite.config import TERMINATE_MESSAGE
from nite.video_mixer import Video, ProcessWithQueue
from nite.video_mixer.video_io import VideoReader
from nite.logging import LogggingProcessConfig, listener_logging_process, configure_process_logging, configure_module_logging

LOGGING_NAME = 'nite.streamer'
logger = configure_module_logging(LOGGING_NAME)


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

    def __init__(
                self,
                videos: List[Video],
                out_width: int,
                out_height: int,
                queue: Queue,
                logging_config: LogggingProcessConfig = None
            ):
        super().__init__(queue=queue)
        self.videos = videos
        self.out_width = out_width
        self.out_height = out_height
        self.ms_to_wait = self._calculate_ms_between_frames()
        self._resize_videos()
        self.logging_config = logging_config
        string_videos = ", ".join([
                                    f'Video {i_vid + 1}: {video.metadata.name}. FPS: {video.metadata.fps}'
                                    for i_vid, video in enumerate(self.videos)
                                ])
        logger.info(
                f"Loaded combiner. {string_videos}. "
                f"Output resolution: {self.out_width}x{self.out_height}. Number of videos: {len(self.videos)}. "
                f"ms to wait between frames: {self.ms_to_wait}"
            )

    def _calculate_ms_between_frames(self):
        sum_fps = sum([video.metadata.fps for video in self.videos])
        average_fps = sum_fps / len(self.videos)
        ms_to_wait = int(1000 / average_fps)
        return ms_to_wait

    def _resize_videos(self):
        for video in self.videos:
            video.resize_frames(self.out_width, self.out_height)

    def stream(self):
        # configure_process_logging(self.logging_config)
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        for frames in zip(*generators):
            received_message = self.receive_from_queue()
            if self.should_terminate(received_message):
                break
            frame = frames[0]
            cv2.imshow("frame combined", frame)
            cv2.waitKey(self.ms_to_wait)
        logger.info("Stream stopped")
        cv2.destroyAllWindows()


def main():
    queue = Queue()

    # log_queue = Queue()
    # logging_config = LogggingProcessConfig(queue=log_queue, logger_name=LOGGING_NAME)
    # log_listener_process = Process(target=listener_logging_process, args=(log_queue,))
    # log_listener_process.start()

    input_frames1 = '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/bunny_video-nite_video'
    input_frames2 = '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/can_video-nite_video'
    video1 = VideoReader().from_frames(input_frames1)
    video2 = VideoReader().from_frames(input_frames2)

    # combiner = VideoCombiner([video1, video2], out_width=640, out_height=480, queue=queue, logging_config=logging_config)
    combiner = VideoCombiner([video1, video2], out_width=640, out_height=480, queue=queue)
    stream_process = Process(target=combiner.stream)
    stream_process.start()

    time.sleep(10)
    queue.put(TERMINATE_MESSAGE)
    stream_process.join()
    # log_queue.put(None)
    # log_listener_process.join()


if __name__ == "__main__":
    main()
