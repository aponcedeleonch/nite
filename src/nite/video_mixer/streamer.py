import time
from typing import List
from multiprocessing import Process, Queue

import cv2
from pydantic import BaseModel

from nite.config import TERMINATE_MESSAGE
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues, Message
from nite.video_mixer.video import Video
from nite.video_mixer.video_io import VideoReader
from nite.video_mixer.audio_listener import AudioListener, AudioActionRMS
from nite.video_mixer.blender import BlendWithAudio, BlendWithAudioThreshold
from nite.video_mixer.audio import short_format

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

    def __init__(self, videos: List[Video], video_stream: VideoStream, queues: CommQueues, blender: BlendWithAudio) -> None:
        super().__init__(queues=queues)
        self.videos = videos
        self._validate_videos()
        self.video_stream = video_stream
        self.ms_to_wait = self._calculate_ms_between_frames()
        self._resize_videos()
        self.blender = blender
        string_videos = ", ".join([
                                    f'Video {i_vid + 1}: {video.metadata.name}. FPS: {video.metadata.fps}'
                                    for i_vid, video in enumerate(self.videos)
                                ])
        logger.info(
                f"Loaded combiner. {string_videos}. "
                f"Output resolution: {self.video_stream}. Number of videos: {len(self.videos)}. "
                f"ms to wait between frames: {self.ms_to_wait}"
            )

    def _validate_videos(self) -> None:
        if not self.videos:
            raise ValueError("No videos to combine")
        if len(self.videos) != 2:
            raise NotImplementedError("For the moment we only support combining 2 videos")

    def _calculate_ms_between_frames(self) -> int:
        sum_fps = sum([video.metadata.fps for video in self.videos])
        average_fps = sum_fps / len(self.videos)
        ms_to_wait = int(1000 / average_fps)
        return ms_to_wait

    def _resize_videos(self) -> None:
        for video in self.videos:
            video.resize_frames(self.video_stream.width, self.video_stream.height)

    def stream(self) -> None:
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        for frames in zip(*generators):
            should_terminate, audio_sample = self.receive()
            if should_terminate:
                break

            frame = self.blender.blend(audio_sample, frames)

            if self.time_recorder.has_period_passed:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

            cv2.imshow("frame combined", frame)
            cv2.waitKey(self.ms_to_wait)
        logger.info("Stream stopped")
        cv2.destroyAllWindows()


class VideoCombinerWithAudio:

    def __init__(
                self,
                video_paths: List[str],
                video_stream: VideoStream,
                playback_time_sec: int,
                blender: BlendWithAudio
            ) -> None:
        queue_to_audio = Queue()
        queue_from_audio = Queue()
        videos = [VideoReader().from_frames(video_path) for video_path in video_paths]
        self.video_queues = CommQueues(in_queue=queue_from_audio, out_queue=queue_to_audio)
        self.audio_queues = CommQueues(in_queue=queue_to_audio, out_queue=queue_from_audio)
        self.video_combiner = VideoCombiner(
            videos=videos,
            video_stream=video_stream,
            blender=blender,
            queues=self.video_queues
        )
        self.audio_detecter = AudioListener(
            queues=self.audio_queues,
            audio_action=blender.audio_action,
            audio_format=short_format
        )
        self.playback_time_sec = playback_time_sec

    def start(self):
        audio_process = Process(target=self.audio_detecter.start)
        audio_process.start()
        stream_process = Process(target=self.video_combiner.stream)
        stream_process.start()

        time.sleep(self.playback_time_sec)

        terminate_message = Message(content=TERMINATE_MESSAGE, content_type='message')
        self.video_queues.in_queue.put(terminate_message)
        self.audio_queues.in_queue.put(terminate_message)
        self.video_queues.in_queue.close()
        self.video_queues.out_queue.close()
        self.video_queues.in_queue.cancel_join_thread()
        self.video_queues.out_queue.cancel_join_thread()
        stream_process.join()
        audio_process.join()


def main():
    input_frames = [
        '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/bunny_video-nite_video',
        # '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/bunny_video-nite_video',
        '/Users/aponcedeleonch/Personal/nite/src/nite/video_mixer/can_video-nite_video'
    ]
    audio_action = AudioActionRMS(audio_format=short_format, threshold=0.2)
    blender = BlendWithAudioThreshold(audio_action=audio_action)
    video_combiner = VideoCombinerWithAudio(
        video_paths=input_frames,
        video_stream=VideoStream(width=640, height=480),
        blender=blender,
        playback_time_sec=10
    )
    video_combiner.start()


if __name__ == "__main__":
    main()
