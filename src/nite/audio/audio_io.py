import asyncio
import struct
from multiprocessing import Queue
from pathlib import Path

import librosa
import numpy as np
import pyaudio
import structlog

from nite.audio.audio import AudioFormat, short_format
from nite.audio.audio_action import AudioActions
from nite.audio.audio_processing import AudioProcessor, AudioSampleFeatures
from nite.config import AUDIO_CHANNELS, AUDIO_SAMPLING_RATE
from nite.video_mixer.time_recorder import TimeRecorder

logger = structlog.get_logger("nite.audio_listener")


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
        """
        The audio listener class is meant to listen to audio coming from the
        microphone and process it using the audio processor and audio actions. If
        there's an action to be taken, given the configured actions, and the detected
        features, it will put the action in the actions queue.

        Args:
            audio_processor: In charge of analyzing the audio samples and detect features.
            audio_actions: The configured actions to take given the detected features.
            actions_queue: The queue to communicate the actions to the video mixer.
            audio_format: The format of the audio samples. Defaults to short_format.
            sample_rate: The sampling rate of the audio. Defaults to AUDIO_SAMPLING_RATE.
            audio_channels: The number of audio channels. Defaults to AUDIO_CHANNELS.

        Returns:
            None
        """
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
        """
        Use the audio processor to get the features of the audio sample.
        """
        audio_sample_features = await self._audio_processor.process_audio_sample(audio_sample)
        return audio_sample_features

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        """
        The callback function that will process the audio block. PyAudio will call this
        function every time it has a new audio block ready and process it in a separate
        thread.
        [Docs](https://people.csail.mit.edu/hubert/pyaudio/docs/#class-pyaudio-stream)

        Steps taken:
        1. Unpack the audio block coming from the microphone.
        2. Get the features of the audio sample.
        3. Ask the audio actions if there's an action to take.
        4. If there's an action, put it in the actions queue to communicate it to the video mixer.
        """
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
        """
        Start the audio listening process. It will open the audio stream and keep it alive
        until a KeyboardInterrupt is received. The audio block processing will be handled
        by the callback function.
        """
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
        """
        Audio analyzer for songs. It will use the audio processor to analyze the audio.
        """
        self.audio_processor = audio_processor

    async def analyze_song(self, song_path: Path) -> AudioSampleFeatures:
        """
        Analyze the song given the path. It will load the song, process the audio sample
        and return the audio features.
        """
        audio_sample, sampling_rate = librosa.load(song_path)
        self.audio_processor.set_sampling_rate(sampling_rate)
        audio_features = await self.audio_processor.process_audio_sample(audio_sample)
        return audio_features
