import asyncio
import struct
from multiprocessing import Queue
from pathlib import Path

import librosa
import numpy as np
import pyaudio

from nite.audio.audio import AudioFormat, short_format
from nite.audio.audio_action import AudioActions
from nite.audio.audio_processing import AudioProcessor, AudioSampleFeatures
from nite.config import AUDIO_CHANNELS, AUDIO_SAMPLING_RATE
from nite.logging import configure_module_logging
from nite.video_mixer import TimeRecorder

logger = configure_module_logging("nite.audio_listener")


class AudioListener:
    def __init__(
        self,
        audio_processor: AudioProcessor,
        audio_actions: AudioActions,
        actions_queue: Queue,
        audio_format: AudioFormat = short_format,
        sample_rate: int = AUDIO_SAMPLING_RATE,
        audio_channels: int = AUDIO_CHANNELS,
    ) -> None:
        self._audio_processor = audio_processor
        self._audio_format = audio_format
        self._sample_rate = sample_rate
        self._audio_channels = audio_channels
        self._audio_actions = audio_actions
        self._actions_queue = actions_queue
        self._audio_processor.set_sampling_rate(sample_rate)
        self._time_recorder = TimeRecorder()
        logger.info(f"Loaded audio listener. Format: {self._audio_format}")

    async def _get_audio_sample_features(self, audio_sample: np.ndarray) -> AudioSampleFeatures:
        audio_sample_features = await self._audio_processor.process_audio_sample(audio_sample)
        return audio_sample_features

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        audio_sample = np.array(
            struct.unpack(self._audio_format.unpack_format % frame_count, in_data)
        )
        audio_sample_features = asyncio.run(self._get_audio_sample_features(audio_sample))
        self._audio_actions.set_features(audio_sample_features)
        should_do_action, blend_strength = asyncio.run(
            self._audio_actions.act(self._time_recorder.elapsed_time_in_ms_since_last_asked)
        )
        if should_do_action:
            self._actions_queue.put(blend_strength)
        return in_data, pyaudio.paContinue

    def start(self) -> None:
        paud = pyaudio.PyAudio()
        stream = paud.open(
            format=self._audio_format.pyaudio_format,
            channels=self._audio_channels,
            rate=self._sample_rate,
            input=True,
            stream_callback=self._process_audio_block,
        )

        logger.info("Starting audio listening")
        self._time_recorder.start_recording_if_not_started()

        try:
            # Keep the stream alive. The callback function will handle the audio processing.
            while stream.is_active():
                if self._time_recorder.has_period_passed:
                    logger.info(f"Keep-alive. Elapsed time: {self._time_recorder.elapsed_time_str}")
        except KeyboardInterrupt:
            logger.info(
                f"Audio listening stopped forcefully. "
                f"Elapsed time: {self._time_recorder.elapsed_time_str}"
            )
        finally:
            logger.info(
                f"Closing audio listening. Elapsed time: {self._time_recorder.elapsed_time_str}"
            )
            stream.close()
            paud.terminate()


class AudioAnalyzerSong:
    def __init__(self, audio_processor: AudioProcessor) -> None:
        self.audio_processor = audio_processor

    async def analyze_song(self, song_path: Path) -> AudioSampleFeatures:
        audio_sample, sampling_rate = librosa.load(song_path)
        self.audio_processor.set_sampling_rate(sampling_rate)
        audio_features = await self.audio_processor.process_audio_sample(audio_sample)
        return audio_features
