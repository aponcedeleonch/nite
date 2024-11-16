from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import Optional, Any, List

import librosa
import numpy as np
from pydantic import BaseModel

from nite.logging import configure_module_logging
from nite.config import AUDIO_SAMPLING_RATE
from nite.video_mixer.audio.audio import AudioFormat
from nite.video_mixer.buffers import Buffer, SampleBuffer

logger = configure_module_logging('nite.audio_processing')


class ChromaIndex(int, Enum):
    c = 0
    c_sharp = 1
    d = 2
    d_sharp = 3
    e = 4
    f = 5
    f_sharp = 6
    g = 7
    g_sharp = 8
    a = 9
    a_sharp = 10
    b = 11


class AudioSampleFeatures(BaseModel):
    bpm: Optional[float] = None
    pitches: Optional[List[ChromaIndex]] = None


class Detector(ABC):

    @abstractmethod
    def detect(self, audio_sample: np.ndarray) -> Optional[Any]:
        pass


class BPMDetector(Detector):

    def __init__(
                self,
                buffer_audio: Buffer = SampleBuffer(),
                buffer_recorded_bpms: Buffer = SampleBuffer(),
                tolerance_threshold: int = 10,
                sampling_rate: int = AUDIO_SAMPLING_RATE,
                reset_after_prediction: bool = False
            ) -> None:
        self.tolerance_threshold = tolerance_threshold
        self.buffer_audio = buffer_audio
        self.buffer_recorded_bpms = buffer_recorded_bpms
        self.sampling_rate = sampling_rate
        self.reset_after_prediction = reset_after_prediction

    def _has_bpm_changed_significantly(self, last_recorded_bpm: float) -> bool:
        if not self.buffer_recorded_bpms.has_enough_data():
            return False

        if len(self.buffer_recorded_bpms()) == 0:
            return False

        distance_to_buffered_bpms = np.abs(last_recorded_bpm - self.buffer_recorded_bpms())
        avg_distance_to_buffered_bpms = np.mean(distance_to_buffered_bpms)
        has_bpm_changed = avg_distance_to_buffered_bpms > self.tolerance_threshold
        return has_bpm_changed

    def _get_avg_recorded_bpms(self) -> Optional[float]:
        if not self.buffer_recorded_bpms.has_enough_data():
            return None
        return np.mean(self.buffer_recorded_bpms())

    def _get_estimated_bpm(self) -> Optional[np.ndarray]:
        if not self.buffer_audio.has_enough_data():
            return None

        # Using this provides a more accurate BPM estimation on longer tracks but is very slow. Not using it
        # _, audio_sample_percussive = librosa.effects.hpss(self.buffer_audio())
        last_recorded_bpm, _ = librosa.beat.beat_track(y=self.buffer_audio(), sr=self.sampling_rate, start_bpm=120)
        if isinstance(last_recorded_bpm, np.ndarray):
            if len(last_recorded_bpm) != 1:
                raise ValueError(f'Beat track returned unexpected BPM: {last_recorded_bpm}. Size: {last_recorded_bpm.shape}')
        elif isinstance(last_recorded_bpm, float):
            last_recorded_bpm = np.array([last_recorded_bpm])
        else:
            raise TypeError(f'Beat track returned unexpected type: {type(last_recorded_bpm)}. Numpy or float expected.')

        return last_recorded_bpm

    async def detect(self, audio_sample: np.ndarray) -> Optional[float]:
        self.buffer_audio.add_sample_to_buffer(audio_sample)

        last_recorded_bpm = self._get_estimated_bpm()
        if last_recorded_bpm is None:
            return None

        # Remove some samples from the buffer to not make predictions so often and slow the process
        if self.reset_after_prediction:
            self.buffer_audio.remove_samples_from_buffer()

        if self._has_bpm_changed_significantly(last_recorded_bpm):
            self.buffer_audio.reset_buffer()
            self.buffer_recorded_bpms.reset_buffer()
            self.buffer_audio.add_sample_to_buffer(audio_sample)

        self.buffer_recorded_bpms.add_sample_to_buffer(last_recorded_bpm)

        return self._get_avg_recorded_bpms()


class PitchDetector(Detector):

    def __init__(
                self,
                buffer_audio: Buffer = SampleBuffer(),
                sampling_rate: int = AUDIO_SAMPLING_RATE,
                reset_after_prediction: bool = False,
                should_return_latest: bool = False,
                hop_length: int = 512
            ) -> None:
        self.buffer_audio = buffer_audio
        self.sampling_rate = sampling_rate
        self.reset_after_prediction = reset_after_prediction
        self.should_return_latest = should_return_latest
        self.hop_length = hop_length

    def _get_chromogram(self) -> np.ndarray:
        estimated_chromogram = librosa.feature.chroma_stft(
                                                            y=self.buffer_audio(),
                                                            sr=self.sampling_rate,
                                                            hop_length=self.hop_length
                                                        )
        if self.should_return_latest:
            return estimated_chromogram[:, -1].reshape(-1, 1)
        return estimated_chromogram

    async def detect(self, audio_sample_normalized: np.ndarray) -> Optional[List[ChromaIndex]]:
        self.buffer_audio.add_sample_to_buffer(audio_sample_normalized)

        if not self.buffer_audio.has_enough_data():
            return None

        if self.reset_after_prediction:
            self.buffer_audio.remove_samples_from_buffer()

        chromogram = self._get_chromogram()
        highest_prob_pitchs = np.argmax(chromogram, axis=0)
        if self.should_return_latest:
            detected_chromas = [ChromaIndex(pitch) for pitch in highest_prob_pitchs]
            return detected_chromas

        chromas_timing = librosa.core.frames_to_time(
                                                    np.arange(len(highest_prob_pitchs)),
                                                    sr=self.sampling_rate,
                                                    hop_length=self.hop_length
                                                )
        time_in_seconds = np.arange(0, round(chromas_timing[-1]))
        detected_chromas_in_sec = np.round(np.interp(time_in_seconds, chromas_timing, highest_prob_pitchs))
        detected_chromas = [ChromaIndex(pitch) for pitch in detected_chromas_in_sec]
        return detected_chromas


class AudioProcessor:

    def __init__(
                self,
                audio_format: Optional[AudioFormat] = None,
                bpm_detector: Optional[BPMDetector] = BPMDetector(),
                pitch_detector: Optional[PitchDetector] = PitchDetector()
            ) -> None:
        if bpm_detector is None and pitch_detector is None:
            raise ValueError('At least one detector must be provided.')

        self.audio_format = audio_format
        self.bpm_detector = bpm_detector
        self.pitch_detector = pitch_detector

    def set_sampling_rate(self, sampling_rate: int) -> None:
        if self.bpm_detector is not None:
            self.bpm_detector.sampling_rate = sampling_rate
        if self.pitch_detector is not None:
            self.pitch_detector.sampling_rate = sampling_rate

    async def process_audio_sample(self, audio_sample: np.ndarray) -> AudioSampleFeatures:
        if self.audio_format is not None:
            audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        else:
            audio_sample_normalized = audio_sample

        task_bpm, task_pitch = None, None
        async with asyncio.TaskGroup() as tg:
            if self.bpm_detector is not None:
                task_bpm = tg.create_task(self.bpm_detector.detect(audio_sample_normalized))
            if self.pitch_detector is not None:
                task_pitch = tg.create_task(self.pitch_detector.detect(audio_sample_normalized))

        bpm, pitch = None, None
        if task_bpm is not None:
            bpm = task_bpm.result()

        if task_pitch is not None:
            pitch = task_pitch.result()

        return AudioSampleFeatures(bpm=bpm, pitches=pitch)
