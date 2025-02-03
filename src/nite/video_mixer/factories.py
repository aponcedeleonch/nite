import asyncio
from abc import ABC, abstractmethod
from multiprocessing import Queue
from pathlib import Path
from typing import List, Optional, Tuple

import nite.config as nite_config
from nite.audio.audio import short_format
from nite.audio.audio_action import (
    AudioAction,
    AudioActionBPM,
    AudioActionPitch,
    AudioActions,
    BPMActionFrequency,
    ChromaIndex,
)
from nite.audio.audio_io import AudioAnalyzerSong, AudioFormat, AudioListener
from nite.audio.audio_processing import AudioProcessor, BPMDetector, PitchDetector
from nite.logging import configure_module_logging
from nite.video.video import VideoFramesPath
from nite.video.video_io import NiteVideo, VideoStream
from nite.video_mixer.blender import BlenderMath, BlendModes, BlendWithSong
from nite.video_mixer.buffers import SampleBuffer
from nite.video_mixer.streamer import (
    VideoCombinerAudioListenerQueue,
    VideoCombinerQueue,
    VideoCombinerSong,
)

logger = configure_module_logging("nite.video_mixer.factories")


class InitMixerError(Exception):
    pass


class NiteFactory(ABC):
    @abstractmethod
    async def get_stream_config(self):
        pass

    @abstractmethod
    async def get_song_config(self):
        pass


class BPMDetectorFactory(NiteFactory):
    def __init__(self, sample_rate: Optional[int]):
        self.sample_rate = sample_rate

    async def get_stream_config(self) -> BPMDetector:
        if self.sample_rate is None:
            raise InitMixerError("Sample rate must be set when initializing audio stream.")
        buffer_audio = SampleBuffer(
            min_buffer_size=nite_config.BPM_BUFFER_SECONDS_MIN * self.sample_rate,
            max_buffer_size=nite_config.BPM_BUFFER_SECONDS_MAX * self.sample_rate,
            num_samples_remove=nite_config.BPM_BUFFER_SECS_REMOVE * self.sample_rate,
        )
        buffer_recorded_bpms = SampleBuffer(
            min_buffer_size=nite_config.BPM_BUFFER_BPMS_MIN,
            max_buffer_size=nite_config.BPM_BUFFER_BPMS_MAX,
        )
        return BPMDetector(
            buffer_audio=buffer_audio,
            buffer_recorded_bpms=buffer_recorded_bpms,
            sampling_rate=self.sample_rate,
        )

    async def get_song_config(self) -> BPMDetector:
        return BPMDetector()


class PitchDetectorFactory(NiteFactory):
    def __init__(self, sample_rate: Optional[int]):
        self.sample_rate = sample_rate

    async def get_stream_config(self) -> PitchDetector:
        if self.sample_rate is None:
            raise InitMixerError("Sample rate must be set when initializing audio stream.")
        # For the moment we are using the same buffer values as BPM. We need to investigate
        # and see if we need to change these values.
        buffer_audio = SampleBuffer(
            min_buffer_size=nite_config.BPM_BUFFER_SECONDS_MIN * self.sample_rate,
            max_buffer_size=nite_config.BPM_BUFFER_SECONDS_MAX * self.sample_rate,
            num_samples_remove=nite_config.BPM_BUFFER_SECS_REMOVE * self.sample_rate,
        )
        return PitchDetector(buffer_audio=buffer_audio, sampling_rate=self.sample_rate)

    async def get_song_config(self) -> PitchDetector:
        return PitchDetector()


class AudioFactory(NiteFactory):
    def __init__(
        self,
        bpm_frequency: Optional[int],
        min_pitch: Optional[int],
        max_pitch: Optional[int],
        blend_falloff: float,
        actions_queue: Optional[Queue] = None,
    ) -> None:
        self._validate_settings(bpm_frequency, min_pitch, max_pitch)
        self.bpm_action = None
        self.pitch_action = None
        self.blend_falloff = blend_falloff

        if bpm_frequency is not None:
            self.bpm_action = AudioActionBPM(BPMActionFrequency(bpm_frequency))

        if min_pitch is not None and max_pitch is not None:
            self.pitch_action = AudioActionPitch(
                min_pitch=ChromaIndex(min_pitch), max_pitch=ChromaIndex(max_pitch)
            )

        self._actions_queue = actions_queue

    def _validate_settings(
        self,
        bpm_frequency: Optional[int],
        min_pitch: Optional[int],
        max_pitch: Optional[int],
    ) -> None:
        if bpm_frequency is None and min_pitch is None and max_pitch is None:
            raise InitMixerError("At least bpm_frequency or min_pitch and max_pitch must be set.")

        if (min_pitch is not None and max_pitch is None) or (
            min_pitch is None and max_pitch is not None
        ):
            raise InitMixerError("Both min_pitch and max_pitch must be set.")

    def _init_audio_actions(self) -> AudioActions:
        actions: List[AudioAction] = []
        if self.bpm_action is not None:
            actions.append(self.bpm_action)
        if self.pitch_action is not None:
            actions.append(self.pitch_action)
        return AudioActions(actions, self.blend_falloff)

    def _init_audio_processor(
        self,
        bpm_detector: Optional[BPMDetector],
        pitch_detector: Optional[PitchDetector],
        audio_format: Optional[AudioFormat],
    ) -> AudioProcessor:
        return AudioProcessor(
            bpm_detector=bpm_detector,
            pitch_detector=pitch_detector,
            audio_format=audio_format,
        )

    async def get_stream_config(self) -> Tuple[AudioListener, AudioActions]:
        if self._actions_queue is None:
            raise InitMixerError("Actions Queue must be set when initializing audio strem.")
        bpm_detector, pitch_detector = None, None
        if self.bpm_action is not None:
            bpm_detector_factory = BPMDetectorFactory(nite_config.AUDIO_SAMPLING_RATE)
            bpm_detector = await bpm_detector_factory.get_stream_config()
        if self.pitch_action is not None:
            pitch_detector_factory = PitchDetectorFactory(nite_config.AUDIO_SAMPLING_RATE)
            pitch_detector = await pitch_detector_factory.get_stream_config()
        audio_actions = self._init_audio_actions()
        audio_processor = self._init_audio_processor(
            bpm_detector, pitch_detector, audio_format=short_format
        )
        return AudioListener(
            actions_queue=self._actions_queue,
            audio_processor=audio_processor,
            audio_actions=audio_actions,
        ), audio_actions

    async def get_song_config(self) -> Tuple[AudioAnalyzerSong, AudioActions]:
        bpm_detector, pitch_detector = None, None
        if self.bpm_action is not None:
            bpm_detector_factory = BPMDetectorFactory(None)
            bpm_detector = await bpm_detector_factory.get_song_config()
        if self.pitch_action is not None:
            pitch_detector_factory = PitchDetectorFactory(None)
            pitch_detector = await pitch_detector_factory.get_song_config()
        audio_actions = self._init_audio_actions()
        audio_processor = self._init_audio_processor(
            bpm_detector, pitch_detector, audio_format=None
        )
        return AudioAnalyzerSong(audio_processor), audio_actions


class VideoFactory(NiteFactory):
    def __init__(
        self,
        width: int,
        height: int,
        video_1: Path,
        video_2: Path,
        alpha: Path,
        blend_operation: str,
        actions_queue: Optional[Queue] = None,
        audio_actions: Optional[AudioActions] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.video_1 = video_1
        self.video_2 = video_2
        self.alpha = alpha
        self.blend_operation = blend_operation
        self._actions_queue = actions_queue
        self.audio_actions = audio_actions

    async def _init(self) -> Tuple[List[VideoFramesPath], BlendWithSong]:
        video_stream = await self._init_video_stream(self.width, self.height)
        async with asyncio.TaskGroup() as tg:
            task_videos = tg.create_task(
                self._init_videos(self.video_1, self.video_2, self.alpha, video_stream)
            )
            task_blender = tg.create_task(self._init_blender(self.blend_operation))
        return task_videos.result(), task_blender.result()

    async def _init_video_stream(self, width: int, height: int) -> VideoStream:
        return VideoStream(width=width, height=height)

    async def _init_videos(
        self, video_1: Path, video_2: Path, alpha: Path, video_stream: VideoStream
    ) -> List[VideoFramesPath]:
        nite_video_1 = NiteVideo(video_1, video_stream)
        nite_video_2 = NiteVideo(video_2, video_stream)
        alpha_video = NiteVideo(alpha, video_stream, is_alpha=True)

        async with asyncio.TaskGroup() as tg:
            task_video_1 = tg.create_task(nite_video_1())
            task_video_2 = tg.create_task(nite_video_2())
            task_alpha = tg.create_task(alpha_video())

        return [task_video_1.result(), task_video_2.result(), task_alpha.result()]

    async def _init_blender(self, blend_operation: str) -> BlendWithSong:
        blender_math = BlenderMath(BlendModes(blend_operation))
        return BlendWithSong(blender_math)

    async def get_stream_config(self) -> VideoCombinerQueue:
        if self._actions_queue is None:
            raise InitMixerError("Actions Queue must be set when initializing video stream.")
        videos, blender = await self._init()
        return VideoCombinerQueue(videos, blender, self._actions_queue)

    async def get_song_config(self) -> VideoCombinerSong:
        if self.audio_actions is None:
            raise InitMixerError("AudioActions must be set when initializing video song.")
        videos, blender = await self._init()
        return VideoCombinerSong(videos, blender, self.audio_actions)


class VideoCombinerFactory:
    def __init__(
        self,
        width: int,
        height: int,
        video_1: Path,
        video_2: Path,
        alpha: Path,
        blend_operation: str,
        min_pitch: Optional[int],
        max_pitch: Optional[int],
        bpm_frequency: Optional[int],
        blend_falloff: float,
        playback_time_sec: Optional[int] = None,
        song_name: Optional[Path] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.video_1 = video_1
        self.video_2 = video_2
        self.alpha = alpha
        self.blend_operation = blend_operation
        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.bpm_frequency = bpm_frequency
        self.blend_falloff = blend_falloff
        self.playback_time_sec = playback_time_sec
        self.song_name = song_name

    async def get_stream_config(self) -> VideoCombinerAudioListenerQueue:
        if self.playback_time_sec is None:
            raise InitMixerError("Playback time must be set when initializing video stream.")

        actions_queue: Queue = Queue()
        video_factory = VideoFactory(
            video_1=self.video_1,
            video_2=self.video_2,
            alpha=self.alpha,
            width=self.width,
            height=self.height,
            blend_operation=self.blend_operation,
            actions_queue=actions_queue,
        )
        audio_factory = AudioFactory(
            bpm_frequency=self.bpm_frequency,
            min_pitch=self.min_pitch,
            max_pitch=self.max_pitch,
            blend_falloff=self.blend_falloff,
            actions_queue=actions_queue,
        )
        video_combiner_queue = await video_factory.get_stream_config()
        audio_listener, _ = await audio_factory.get_stream_config()
        return VideoCombinerAudioListenerQueue(
            video_combiner_queue=video_combiner_queue,
            audio_listener=audio_listener,
            playback_time_sec=self.playback_time_sec,
            actions_queue=actions_queue,
        )

    async def get_song_config(self) -> VideoCombinerSong:
        if self.song_name is None:
            raise InitMixerError("Song name must be set when initializing video song.")
        audio_factory = AudioFactory(
            bpm_frequency=self.bpm_frequency,
            min_pitch=self.min_pitch,
            max_pitch=self.max_pitch,
            blend_falloff=self.blend_falloff,
        )
        audio_analyzer, audio_actions = await audio_factory.get_song_config()
        audio_features = await audio_analyzer.analyze_song(self.song_name)
        logger.info(f"Audio features detected: {audio_features}")
        audio_actions.set_features(audio_features)
        video_factory = VideoFactory(
            video_1=self.video_1,
            video_2=self.video_2,
            alpha=self.alpha,
            width=self.width,
            height=self.height,
            blend_operation=self.blend_operation,
            audio_actions=audio_actions,
        )
        video_combiner_song = await video_factory.get_song_config()
        return video_combiner_song
