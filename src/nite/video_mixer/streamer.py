import time
from typing import List
from multiprocessing import Process, Queue

import cv2

from nite.config import TERMINATE_MESSAGE
from nite.logging import configure_module_logging
from nite.video_mixer import CommQueues, Message, TimeRecorder
from nite.video_mixer.audio.audio import short_format
from nite.video_mixer.audio.audio_action import AudioActions
from nite.video_mixer.blender import BlendWithAudio, BlendWithSong
from nite.video_mixer.video.video import VideoFramesPath
from nite.video_mixer.video.video_io import VideoReader, VideoStream
from nite.video_mixer.audio.audio_io import AudioListener

LOGGING_NAME = 'nite.streamer'
logger = configure_module_logging(LOGGING_NAME)


class VideoCombinerSong:

    def __init__(
                self,
                videos: List[VideoFramesPath],
                blender: BlendWithSong,
                actions: AudioActions,
                blend_falloff_sec: float
            ) -> None:
        self.time_recorder = TimeRecorder()
        self.videos = videos
        self._validate_videos()
        self.ms_to_wait = self._calculate_ms_between_frames()
        self.blender = blender
        self.actions = actions
        self.blend_falloff_sec = blend_falloff_sec
        string_videos = ", ".join([
                                    f'Video {i_vid + 1}: {video.metadata.name}. FPS: {video.metadata.fps}'
                                    for i_vid, video in enumerate(self.videos)
                                ])
        logger.info(
                f"Loaded combiner. {string_videos}. "
                f"Number of videos: {len(self.videos)}. "
                f"ms to wait between frames: {self.ms_to_wait}"
            )

    def _validate_videos(self) -> None:
        if not self.videos:
            raise ValueError("No videos to combine")
        if not (2 <= len(self.videos) <= 3):
            raise NotImplementedError("For the moment we only support combining 2 videos and an alpha")

    def _calculate_ms_between_frames(self) -> int:
        sum_fps = sum([video.metadata.fps for video in self.videos])
        average_fps = sum_fps / len(self.videos)
        ms_to_wait = int(1000 / average_fps)
        return ms_to_wait

    async def stream(self) -> None:
        generators = [video.circular_frame_generator() for video in self.videos]
        logger.info("Starting stream")
        self.time_recorder.start_recording_if_not_started()
        try:
            for frames in zip(*generators):
                should_blend, blend_strength = await self.actions.act(self.ms_to_wait, self.blend_falloff_sec)
                frame = self.blender.blend(frames, should_blend=should_blend, blend_strength=blend_strength)

                if self.time_recorder.has_period_passed:
                    logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

                cv2.imshow("frame combined", frame)
                cv2.waitKey(self.ms_to_wait)
        except KeyboardInterrupt:
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
        queue_to_audio: Queue = Queue()
        queue_from_audio: Queue = Queue()
        videos = [
                    VideoReader().from_frames(video_path, video_stream.width, video_stream.height)
                    for video_path in video_paths
                ]
        self.video_queues = CommQueues(in_queue=queue_from_audio, out_queue=queue_to_audio)
        self.audio_queues = CommQueues(in_queue=queue_to_audio, out_queue=queue_from_audio)
        self.video_combiner = VideoCombinerSong(
            videos=videos,
            video_stream=video_stream,
            blender=blender,
            queues=self.video_queues
        )
        self.audio_detecter = AudioListener(
            queues=self.audio_queues,
            audio_actions=blender.audio_actions,
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
