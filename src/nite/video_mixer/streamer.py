import asyncio
import time
from abc import ABC, abstractmethod
from multiprocessing import Process
from typing import List

import cv2

from nite.audio.audio_action import AudioActions
from nite.audio.audio_io import AudioListener
from nite.config import TERMINATE_MESSAGE
from nite.logging import configure_module_logging
from nite.video.video import VideoFramesPath
from nite.video_mixer import Message, QueueHandler, TimeRecorder
from nite.video_mixer.blender import BlendWithSong

logger = configure_module_logging("nite.streamer")


class VideoCombiner(ABC):
    def __init__(self, videos: List[VideoFramesPath], blender: BlendWithSong) -> None:
        self.time_recorder = TimeRecorder()
        self.videos = videos
        self._validate_videos()
        self.ms_to_wait = self._calculate_ms_between_frames()
        self.blender = blender
        string_videos = ", ".join(
            [
                f"Video {i_vid + 1}: {video.metadata.name}. FPS: {video.metadata.fps}"
                for i_vid, video in enumerate(self.videos)
            ]
        )
        logger.info(
            f"Loaded combiner. {string_videos}. "
            f"Number of videos: {len(self.videos)}. "
            f"ms to wait between frames: {self.ms_to_wait}"
        )

    def _validate_videos(self) -> None:
        if not self.videos:
            raise ValueError("No videos to combine")
        if not (2 <= len(self.videos) <= 3):
            raise NotImplementedError(
                "For the moment we only support combining 2 videos and an alpha"
            )

    def _calculate_ms_between_frames(self) -> int:
        sum_fps = sum([video.metadata.fps for video in self.videos])
        average_fps = sum_fps / len(self.videos)
        ms_to_wait = int(1000 / average_fps)
        return ms_to_wait

    @abstractmethod
    def stream(self) -> None:
        pass


class VideoCombinerSong(VideoCombiner):
    def __init__(
        self,
        videos: List[VideoFramesPath],
        blender: BlendWithSong,
        actions: AudioActions,
    ) -> None:
        super().__init__(videos, blender)
        self.actions = actions

    def stream(self) -> None:
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        self.time_recorder.start_recording_if_not_started()
        try:
            for frames in zip(*generators):
                should_blend, blend_strength = asyncio.run(self.actions.act(self.ms_to_wait))
                frame = self.blender.blend(
                    frames, should_blend=should_blend, blend_strength=blend_strength
                )

                if self.time_recorder.has_period_passed:
                    logger.info(f"Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}")

                cv2.imshow("frame combined", frame)
                cv2.waitKey(self.ms_to_wait)
        except KeyboardInterrupt:
            logger.info("Stream stopped")
            cv2.destroyAllWindows()


class VideoCombinerQueue(VideoCombiner):
    def __init__(
        self,
        videos: List[VideoFramesPath],
        blender: BlendWithSong,
        queue_handler: QueueHandler,
    ) -> None:
        super().__init__(videos, blender)
        self.queue_handler = queue_handler

    def stream(self) -> None:
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        self.time_recorder.start_recording_if_not_started()
        for frames in zip(*generators):
            should_terminate, blend_strength = self.queue_handler.receive_blend_strength()
            if should_terminate:
                logger.info("Video stream stopped by terminate message")
                break

            if blend_strength is not None:
                should_blend = True
            else:
                should_blend = False
                blend_strength = 0
            frame = self.blender.blend(
                frames, should_blend=should_blend, blend_strength=blend_strength
            )

            if self.time_recorder.has_period_passed:
                logger.info(f"Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}")

            cv2.imshow("frame combined", frame)
            cv2.waitKey(self.ms_to_wait)

        logger.info(f"Stream stopped. Elapsed time: {self.time_recorder.elapsed_time_str}")
        cv2.destroyAllWindows()


class VideoCombinerAudioListenerQueue(VideoCombiner):
    def __init__(
        self,
        video_combiner_queue: VideoCombinerQueue,
        audio_listener: AudioListener,
        playback_time_sec: int,
    ) -> None:
        self.video_combiner_queue = video_combiner_queue
        self.audio_listener = audio_listener
        self.playback_time_sec = playback_time_sec

    def stream(self) -> None:
        try:
            audio_process = Process(target=self.audio_listener.start)
            audio_process.start()
            stream_process = Process(target=self.video_combiner_queue.stream)
            stream_process.start()

            time.sleep(self.playback_time_sec)
        except KeyboardInterrupt:
            logger.info("Stream stopped forcefully")

        terminate_message = Message(content=TERMINATE_MESSAGE, content_type="message")
        logger.info("Sending terminate message to video combiner")
        self.video_combiner_queue.queue_handler.in_queue.put(terminate_message)
        time.sleep(1)
        logger.info("Sending terminate message to audio listener")
        self.audio_listener.queue_handler.in_queue.put(terminate_message)
        time.sleep(1)
        self.video_combiner_queue.queue_handler.cleanup()
        stream_process.join(timeout=2)
        audio_process.join(timeout=2)
