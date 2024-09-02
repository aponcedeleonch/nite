import sys
import struct
from abc import ABC, abstractmethod

import pyaudio
import numpy as np

from nite.config import AUDIO_SAMPLING_RATE
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues
from nite.video_mixer.audio import AudioFormat


LOGGING_NAME = 'nite.audio_listener'
logger = configure_module_logging(LOGGING_NAME)

# Need to still investigate what is CHANNELS.
CHANNELS = 1 if sys.platform == 'darwin' else 2


class AudioAction(ABC):

    def __init__(self, audio_format: AudioFormat):
        self.audio_format = audio_format

    @abstractmethod
    def process(self, audio_sample: np.ndarray):
        pass


class AudioActionRMS(AudioAction):

    def __init__(self, audio_format: AudioFormat, threshold: float):
        super().__init__(audio_format)
        self.threshold = threshold
        logger.info(f'Loaded threshold blender. Threshold: {threshold}')

    def _calculate_rms(self, audio_sample: np.ndarray) -> float:
        audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        audio_rms = np.sqrt(np.mean(audio_sample_normalized ** 2))
        return audio_rms

    def process(self, audio_sample: np.ndarray) -> float:
        audio_rms = self._calculate_rms(audio_sample)
        logger.debug(f'RMS: {audio_rms}. Audio sample: {audio_sample}.')
        if audio_rms > self.threshold:
            return audio_sample[:1]
        return None


class AudioListener(ProcessWithQueue):

    def __init__(self, queues: CommQueues, audio_action: AudioAction, audio_format: AudioFormat):
        super().__init__(queues=queues)
        self.audio_format = audio_format
        self.audio_action = audio_action
        logger.info(f'Loaded audio listener. Format: {self.audio_format}')

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        audio_sample = np.array(struct.unpack(self.audio_format.unpack_format % frame_count, in_data))
        postprocessed_audio_sample = self.audio_action.process(audio_sample)
        if postprocessed_audio_sample is not None:
            self.send_audio_sample(audio_sample)
        return in_data, pyaudio.paContinue

    def start(self) -> None:
        paud = pyaudio.PyAudio()
        stream = paud.open(
                            format=self.audio_format.pyaudio_format,
                            channels=CHANNELS,
                            rate=AUDIO_SAMPLING_RATE,
                            input=True,
                            stream_callback=self._process_audio_block
                        )

        logger.info('Starting audio listening')
        while stream.is_active():
            should_terminate, _ = self.receive()
            if should_terminate:
                break

            if self.time_recorder.has_period_passed:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

        stream.close()
        paud.terminate()
        logger.info(f'Audio listening stopped. Elapsed time: {self.time_recorder.elapsed_time_str}')
