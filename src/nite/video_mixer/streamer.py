import asyncio
import time
from abc import ABC, abstractmethod
from multiprocessing import Process, Queue
from queue import Empty as QueueEmpty
from typing import List

import cv2
import structlog

from nite.audio.audio_action import AudioActions
from nite.audio.audio_io import AudioListener
from nite.video.video import VideoFramesPath
from nite.video_mixer.blender import BlendWithSong
from nite.video_mixer.time_recorder import TimeRecorder

logger = structlog.get_logger("nite.streamer")


class TerminateTaskGroupError(Exception):
    """Exception raised to terminate a task group."""


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
                    frames,  # type: ignore[arg-type]
                    should_blend=should_blend,
                    blend_strength=blend_strength,
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
        actions_queue: Queue,
    ) -> None:
        super().__init__(videos, blender)
        self._actions_queue = actions_queue

    def stream(self) -> None:
        """
        Get the frames from the videos and blend them. The blend strength will be received from the
        actions queue.
        """

        # Combine the frames from the videos to iterate infinitely over them
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        self.time_recorder.start_recording_if_not_started()
        try:
            # Iterate over the frames and blend them
            for frames in zip(*generators):
                try:
                    blend_strength = self._actions_queue.get_nowait()
                except QueueEmpty:
                    # No blend strength received
                    blend_strength = None

                if blend_strength is not None:
                    should_blend = True
                else:
                    should_blend = False
                    blend_strength = 0

                # Get the blended frame
                frame = self.blender.blend(
                    frames,  # type: ignore[arg-type]
                    should_blend=should_blend,
                    blend_strength=blend_strength,
                )

                if self.time_recorder.has_period_passed:
                    logger.info(f"Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}")

                # Show the blended frame using OpenCV
                cv2.imshow("frame combined", frame)
                cv2.waitKey(self.ms_to_wait)
        except KeyboardInterrupt:
            logger.info(
                f"Stream stopped forcefully. Elapsed time: {self.time_recorder.elapsed_time_str}"
            )
        finally:
            logger.info(f"Stream finished. Elapsed time: {self.time_recorder.elapsed_time_str}")
            cv2.destroyAllWindows()


class VideoCombinerAudioListenerQueue(VideoCombiner):
    def __init__(
        self,
        video_combiner_queue: VideoCombinerQueue,
        audio_listener: AudioListener,
        playback_time_sec: int,
        actions_queue: Queue,
    ) -> None:
        self._video_combiner_queue = video_combiner_queue
        self._audio_listener = audio_listener
        self._playback_time_sec = playback_time_sec
        self._actions_queue = actions_queue

    def stream(self) -> None:
        """
        Run the stream for the given playback time. The audio listener will start the audio
        processing and the video combiner will combine the video frames with the audio actions.

        Both the audio listener and the video combiner will run in separate processes.
        """
        logger.info(f"Starting stream for {self._playback_time_sec} seconds")

        video_combiner_sub = Process(target=self._video_combiner_queue.stream, daemon=True)
        audio_listener_sub = Process(target=self._audio_listener.start, daemon=True)

        video_combiner_sub.start()
        audio_listener_sub.start()

        try:
            time.sleep(self._playback_time_sec)
            logger.info("Stream finished")
        except KeyboardInterrupt:
            logger.info("Stream stopped forcefully")
        finally:
            audio_listener_sub.terminate()
            video_combiner_sub.terminate()
            self._actions_queue.close()
