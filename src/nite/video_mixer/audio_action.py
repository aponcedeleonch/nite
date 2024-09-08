from abc import ABC, abstractmethod
from enum import Enum

import numpy as np

from nite.logging import configure_module_logging
from nite.video_mixer import TimeRecorder
from nite.video_mixer.audio import AudioFormat

LOGGING_NAME = 'nite.audio_action'
logger = configure_module_logging(LOGGING_NAME)


class BPMActionFrequency(float, Enum):
    kick = 0
    compass = 1
    two_compass = 2
    four_compass = 4


class AudioAction(ABC):

    def __init__(self):
        pass

    @abstractmethod
    def process(self, audio_sample: np.ndarray) -> bool:
        pass


class AudioActionBPM(AudioAction):

    def __init__(self, bpm: int, bpm_action_frequency: BPMActionFrequency, beats_per_compass: int = 4) -> None:
        super().__init__()
        bar_duration_sec = self._calculate_bar_duration_seconds(bpm, beats_per_compass)
        action_period = self._calculate_action_period(bar_duration_sec, bpm_action_frequency, beats_per_compass)
        logger.info(
            f'Loaded audio action BPM. BPM: {bpm}. '
            f'Beats per compass: {beats_per_compass}. '
            f'Bar duration in sec: {bar_duration_sec}. '
            f'Frequency: {bpm_action_frequency}. '
            f'Action period: {action_period}'
        )
        self.time_recorder = TimeRecorder(period_timeout_sec=action_period)

    def _calculate_bar_duration_seconds(self, bpm: int, beats_per_compass: int) -> float:
        return beats_per_compass / bpm * 60

    def _calculate_action_period(self, bar_duration_sec: float, bpm_action_frequency: float, beats_per_compass: int) -> float:
        if bpm_action_frequency == BPMActionFrequency.kick:
            return bar_duration_sec / beats_per_compass
        else:
            return bar_duration_sec * bpm_action_frequency

    def process(self, audio_sample: np.ndarray) -> bool:
        self.time_recorder.start_recording_if_not_started()
        if self.time_recorder.has_period_passed:
            return True
        return False


class AudioActionRMS(AudioAction):

    def __init__(self, audio_format: AudioFormat, threshold: float):
        super().__init__()
        self.audio_format = audio_format
        self.threshold = threshold
        logger.info(f'Loaded audio action RMS. Threshold: {threshold}')

    def _calculate_rms(self, audio_sample: np.ndarray) -> float:
        audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        audio_rms = np.sqrt(np.mean(audio_sample_normalized ** 2))
        return audio_rms

    def process(self, audio_sample: np.ndarray) -> bool:
        audio_rms = self._calculate_rms(audio_sample)
        logger.debug(f'RMS: {audio_rms}. Audio sample: {audio_sample}.')
        if audio_rms > self.threshold:
            return True
        return False
