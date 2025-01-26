import asyncio
import struct

import librosa
import numpy as np
import pyaudio

from nite.audio.audio import AudioFormat, short_format
from nite.audio.audio_action import AudioActions
from nite.audio.audio_processing import AudioProcessor
from nite.config import AUDIO_CHANNELS, AUDIO_SAMPLING_RATE
from nite.logging import configure_module_logging
from nite.video_mixer import QueueHandler, TimeRecorder

logger = configure_module_logging("nite.audio_listener")


class AudioListener:
    def __init__(
        self,
        queue_handler: QueueHandler,
        audio_processor: AudioProcessor,
        audio_actions: AudioActions,
        audio_format: AudioFormat = short_format,
        sample_rate: int = AUDIO_SAMPLING_RATE,
        audio_channels: int = AUDIO_CHANNELS,
    ) -> None:
        self.queue_handler = queue_handler
        self.audio_processor = audio_processor
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.audio_channels = audio_channels
        self.audio_actions = audio_actions
        self.audio_processor.set_sampling_rate(sample_rate)
        self.time_recorder = TimeRecorder()
        logger.info(f"Loaded audio listener. Format: {self.audio_format}")

    async def _get_audio_sample_features(self, audio_sample: np.ndarray) -> bool:
        audio_sample_features = await self.audio_processor.process_audio_sample(audio_sample)
        return audio_sample_features

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        audio_sample = np.array(
            struct.unpack(self.audio_format.unpack_format % frame_count, in_data)
        )
        audio_sample_features = asyncio.run(self._get_audio_sample_features(audio_sample))
        self.audio_actions.set_features(audio_sample_features)
        should_do_action, blend_strength = asyncio.run(
            self.audio_actions.act(self.time_recorder.elapsed_time_in_ms_since_last_asked)
        )
        if should_do_action:
            self.queue_handler.send_blend_strength(blend_strength)
        return in_data, pyaudio.paContinue

    def start(self) -> None:
        paud = pyaudio.PyAudio()
        stream = paud.open(
            format=self.audio_format.pyaudio_format,
            channels=self.audio_channels,
            rate=self.sample_rate,
            input=True,
            stream_callback=self._process_audio_block,
        )

        logger.info("Starting audio listening")
        self.time_recorder.start_recording_if_not_started()
        while stream.is_active():
            should_terminate, _ = self.queue_handler.receive_blend_strength()
            if should_terminate:
                logger.info("Audio Listener stopped by terminate message")
                break

            if self.time_recorder.has_period_passed:
                logger.info(f"Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}")

        stream.close()
        paud.terminate()
        logger.info(f"Audio listening stopped. Elapsed time: {self.time_recorder.elapsed_time_str}")


class AudioAnalyzerSong:
    def __init__(self, audio_processor: AudioProcessor) -> None:
        self.audio_processor = audio_processor

    async def analyze_song(self, song_path: str) -> None:
        audio_sample, sampling_rate = librosa.load(song_path)
        self.audio_processor.set_sampling_rate(sampling_rate)
        audio_features = await self.audio_processor.process_audio_sample(audio_sample)
        return audio_features
