import asyncio
from abc import ABC, abstractmethod
from typing import List

import cv2

from nite.audio.audio_action import AudioActions
from nite.audio.audio_io import AudioListener
from nite.logging import configure_module_logging
from nite.video.video import VideoFramesPath
from nite.video_mixer import TimeRecorder
from nite.video_mixer.blender import BlendWithSong

logger = configure_module_logging("nite.streamer")

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

    async def stream(self) -> None:
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
        actions_queue: asyncio.Queue,
    ) -> None:
        super().__init__(videos, blender)
        self._actions_queue = actions_queue

    async def stream(self) -> None:
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        self.time_recorder.start_recording_if_not_started()
        try:
            for frames in zip(*generators):
                try:
                    blend_strength = self._actions_queue.get_nowait()
                except asyncio.QueueEmpty:
                    # No blend strength received
                    blend_strength = None

                if blend_strength is not None:
                    should_blend = True
                else:
                    should_blend = False
                    blend_strength = 0
                frame = self.blender.blend(
                    frames,  # type: ignore[arg-type]
                    should_blend=should_blend,
                    blend_strength=blend_strength,
                )

                if self.time_recorder.has_period_passed:
                    logger.info(f"Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}")

                cv2.imshow("frame combined", frame)
                cv2.waitKey(self.ms_to_wait)
        except asyncio.CancelledError:
            logger.info(f"Stream stopped. Elapsed time: {self.time_recorder.elapsed_time_str}")
        finally:
            cv2.destroyAllWindows()


class VideoCombinerAudioListenerQueue(VideoCombiner):
    def __init__(
        self,
        video_combiner_queue: VideoCombinerQueue,
        audio_listener: AudioListener,
        playback_time_sec: int,
        actions_queue: asyncio.Queue,
    ) -> None:
        self._video_combiner_queue = video_combiner_queue
        self._audio_listener = audio_listener
        self._playback_time_sec = playback_time_sec
        self._actions_queue = actions_queue

    async def force_terminate_task_group():
        """Used to force termination of a task group."""
        raise TerminateTaskGroupError()

    async def stream(self) -> None:
        try:
            async with asyncio.TaskGroup() as group:
                # spawn the audio listener with the video combiner
                group.create_task(self._video_combiner_queue.stream())
                group.create_task(self._audio_listener.start())

                await asyncio.sleep(self._playback_time_sec)
                # add an exception-raising task to force the group to terminate
                group.create_task(self.force_terminate_task_group())
        except KeyboardInterrupt:
            logger.info("Stream stopped forcefully")
        except TerminateTaskGroupError:
            logger.info("Stream stopped")
        finally:
            self._actions_queue.shutdown()
