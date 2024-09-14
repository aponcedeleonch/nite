from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import numpy as np
import librosa

from nite.config import AUDIO_SAMPLING_RATE
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


class BPMDetecter:

    def __init__(self, change_threshold: int = 10, seconds_in_buffer: int = 5, min_seconds_in_buffer: int = 4) -> None:
        self.audio_buffer = np.zeros(0)
        self.detected_bpm = None
        self.bpm_change_threshold = change_threshold
        self.seconds_in_buffer = seconds_in_buffer
        self.min_seconds_in_buffer = min_seconds_in_buffer

    def _reset_buffer(self) -> None:
        self.audio_buffer = np.zeros(0)

    def _has_bpm_changed_significantly(self, new_detected_bpm: int) -> bool:
        return abs(new_detected_bpm - self.detected_bpm) > self.bpm_change_threshold

    def _has_enough_audio_data(self) -> bool:
        return len(self.audio_buffer) >= self.min_seconds_in_buffer * AUDIO_SAMPLING_RATE

    def _add_audio_sample_to_buffer(self, audio_sample: np.ndarray) -> None:
        self.audio_buffer = np.append(self.audio_buffer, audio_sample, axis=0)
        self.audio_buffer = self.audio_buffer[-self.seconds_in_buffer * AUDIO_SAMPLING_RATE:]

    def _set_detected_bpm(self, new_detected_bpm: int) -> None:
        self.detected_bpm = (self.detected_bpm + new_detected_bpm) / 2

    def _get_estimated_bpm(self) -> Optional[int]:
        # If we don't have enough audio data, we can't detect BPM
        if not self._has_enough_audio_data():
            return None

        new_detected_bpm, _ = librosa.beat.beat_track(y=self.audio_buffer, sr=AUDIO_SAMPLING_RATE)
        if isinstance(new_detected_bpm, np.ndarray):
            if len(new_detected_bpm) != 1:
                raise ValueError(f'Beat track returned more than one BPM: {new_detected_bpm}. Size: {len(new_detected_bpm)}')
            new_detected_bpm_rounded = int(new_detected_bpm[0])
        return new_detected_bpm_rounded

    def detect_bpm(self, audio_sample: np.ndarray) -> Optional[int]:
        self._add_audio_sample_to_buffer(audio_sample)

        new_detected_bpm = self._get_estimated_bpm()
        if new_detected_bpm is None:
            return self.detected_bpm

        if self.detected_bpm is None:
            self.detected_bpm = new_detected_bpm
            logger.info(f'Original Detected BPM: {self.detected_bpm}')
        else:
            if self._has_bpm_changed_significantly(new_detected_bpm):
                logger.info(f'Significant BPM change. Current: {self.detected_bpm}. New: {new_detected_bpm}')
                self.detected_bpm = new_detected_bpm
                self._reset_buffer()
            else:
                self._set_detected_bpm(new_detected_bpm)

        return self.detected_bpm


class AudioActionBPM(AudioAction):

    def __init__(self, bpm_action_frequency: BPMActionFrequency, beats_per_compass: int = 4) -> None:
        super().__init__()
        self.beats_per_compass = beats_per_compass
        self.bpm_action_frequency = bpm_action_frequency
        self.bpm_detecter = BPMDetecter()
        logger.info(
            f'Beats per compass: {beats_per_compass}. '
            f'Frequency: {bpm_action_frequency}. '
        )
        self.time_recorder = TimeRecorder(period_timeout_sec=np.inf)

    def _calculate_bar_duration_seconds(self, bpm: int, beats_per_compass: int) -> float:
        return beats_per_compass / bpm * 60

    def _calculate_action_period(self, bar_duration_sec: float, bpm_action_frequency: float, beats_per_compass: int) -> float:
        if bpm_action_frequency == BPMActionFrequency.kick:
            return bar_duration_sec / beats_per_compass
        else:
            return bar_duration_sec * bpm_action_frequency

    def _calculate_period_timeout_sec(self, bpm: int) -> float:
        bar_duration_sec = self._calculate_bar_duration_seconds(bpm, self.beats_per_compass)
        return self._calculate_action_period(bar_duration_sec, self.bpm_action_frequency, self.beats_per_compass)

    def process(self, audio_sample: np.ndarray) -> bool:
        bpm = self.bpm_detecter.detect_bpm(audio_sample)
        if bpm is None:
            return False

        action_period_timeout = self._calculate_period_timeout_sec(bpm)
        self.time_recorder.period_timeout_sec = action_period_timeout
        self.time_recorder.start_recording_if_not_started()
        if self.time_recorder.has_period_passed:
            logger.info(f'BPM: {bpm}. Action frequency: {self.bpm_action_frequency}. Action period: {action_period_timeout}.')
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
