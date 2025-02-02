import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional

import librosa
import numpy as np
from pydantic import BaseModel

from nite.audio.audio import AudioFormat
from nite.config import AUDIO_SAMPLING_RATE
from nite.logging import configure_module_logging
from nite.video_mixer.buffers import Buffer, SampleBuffer

logger = configure_module_logging("nite.audio_processing")


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
    """
    Available features to detect from the audio samples.
    """

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
        sampling_rate: float = AUDIO_SAMPLING_RATE,
        reset_after_prediction: bool = False,
    ) -> None:
        """
        BPM detector class to detect the BPM of the audio samples.

        Initializing the buffer_audio empty will create an empty limitless buffer.
        The reset_after_prediction parameter will reset the buffer after a prediction is made.
        Can be used to not make predictions too often.
        """
        self.tolerance_threshold = tolerance_threshold
        self.buffer_audio = buffer_audio
        self.buffer_recorded_bpms = buffer_recorded_bpms
        self.sampling_rate = sampling_rate
        self.reset_after_prediction = reset_after_prediction

    def _has_bpm_changed_significantly(self, last_recorded_bpm: np.ndarray) -> bool:
        """
        Heuristic to check if the BPM has changed significantly.
        """
        # If we don't have enough data, we can't make a prediction
        if not self.buffer_recorded_bpms.has_enough_data():
            return False
        if len(self.buffer_recorded_bpms.buffered_data) == 0:
            return False

        # Calculate the absolute distance to the buffered BPMs
        distance_to_buffered_bpms = np.abs(
            last_recorded_bpm - self.buffer_recorded_bpms.buffered_data
        )

        # Calculate the average distance to the buffered BPMs
        avg_distance_to_buffered_bpms = np.mean(distance_to_buffered_bpms)

        # Check if the average distance is greater than the tolerance threshold.
        # If it is, the BPM has changed significantly.
        has_bpm_changed = avg_distance_to_buffered_bpms > self.tolerance_threshold
        return has_bpm_changed

    def _get_avg_recorded_bpms(self) -> Optional[float]:
        if not self.buffer_recorded_bpms.has_enough_data():
            return None
        return np.mean(self.buffer_recorded_bpms.buffered_data)

    def _get_estimated_bpm(self) -> Optional[np.ndarray]:
        """
        Here is where we estimate the BPM of the audio samples using the librosa library.
        """
        # If we don't have enough data, we can't make a prediction
        if not self.buffer_audio.has_enough_data():
            return None

        # Using this provides a more accurate BPM estimation on longer tracks but is very slow.
        # _, audio_sample_percussive = librosa.effects.hpss(self.buffer_audio.buffered_data)
        last_recorded_bpm, _ = librosa.beat.beat_track(
            y=self.buffer_audio.buffered_data, sr=self.sampling_rate, start_bpm=120
        )
        # Standardize the BPM prediction to be a numpy array
        if isinstance(last_recorded_bpm, np.ndarray):
            if len(last_recorded_bpm) != 1:
                raise ValueError(
                    f"Unexpected BPM: {last_recorded_bpm}. Size: {last_recorded_bpm.shape}"
                )
        elif isinstance(last_recorded_bpm, float):
            last_recorded_bpm = np.array([last_recorded_bpm])
        else:
            raise TypeError(
                f"Unexpected BPM type: {type(last_recorded_bpm)}. Numpy or float expected."
            )

        return last_recorded_bpm

    async def detect(self, audio_sample: np.ndarray) -> Optional[float]:
        """
        Detect the BPM of the audio samples using the librosa library.
        """
        # Add the audio sample to the buffer
        self.buffer_audio.add_sample_to_buffer(audio_sample)

        # Get the estimated BPM
        last_recorded_bpm = self._get_estimated_bpm()
        if last_recorded_bpm is None:
            return None

        # Remove some samples from the buffer to not make predictions so often and slow the process
        if self.reset_after_prediction:
            self.buffer_audio.remove_samples_from_buffer()

        # Heuristic to reset the buffer if the BPM has changed significantly
        # In theory, the buffer should not change significantly with the same song.
        # If it does, it means that the song has changed.
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
        sampling_rate: float = AUDIO_SAMPLING_RATE,
        reset_after_prediction: bool = False,
        should_return_latest: bool = False,
        hop_length: int = 512,
    ) -> None:
        """
        Pitch detector class to detect the pitch of the audio samples.

        Initializing the buffer_audio empty will create an empty limitless buffer.
        The reset_after_prediction parameter will reset the buffer after a prediction is made.
        Can be used to not make predictions too often.
        """
        self.buffer_audio = buffer_audio
        self.sampling_rate = sampling_rate
        self.reset_after_prediction = reset_after_prediction
        self.should_return_latest = should_return_latest
        self.hop_length = hop_length

    def _get_chromogram(self) -> np.ndarray:
        """
        Make the chromogram estimation using the STFT method.

        Here we're estimating the chroma (pitch) of the audio samples.
        [Docs](https://librosa.org/doc/0.10.2/generated/librosa.feature.chroma_stft.html)
        """
        estimated_chromogram = librosa.feature.chroma_stft(
            y=self.buffer_audio.buffered_data, sr=self.sampling_rate, hop_length=self.hop_length
        )
        if self.should_return_latest:
            return estimated_chromogram[:, -1].reshape(-1, 1)
        return estimated_chromogram

    async def detect(self, audio_sample_normalized: np.ndarray) -> Optional[List[ChromaIndex]]:
        """
        Detect the pitch of the audio samples using the chroma estimation.
        """
        # Add the audio sample to the buffer
        self.buffer_audio.add_sample_to_buffer(audio_sample_normalized)

        # If we don't have enough data, we can't make a prediction
        if not self.buffer_audio.has_enough_data():
            return None

        # Get the chromogram estimation
        chromogram = self._get_chromogram()

        # Remove some samples from the buffer to not make predictions so often and slow the process
        if self.reset_after_prediction:
            self.buffer_audio.remove_samples_from_buffer()

        # Only pick the highest probability pitch. The chromogram is a 12xN matrix. Where
        # N is the number of frames and 12 is the number of pitches.
        highest_prob_pitchs = np.argmax(chromogram, axis=0)
        if self.should_return_latest:
            detected_chromas = [ChromaIndex(pitch) for pitch in highest_prob_pitchs]
            return detected_chromas

        # Get the detected chromas frames in seconds
        chromas_timing = librosa.core.frames_to_time(
            np.arange(len(highest_prob_pitchs)),
            sr=self.sampling_rate,
            hop_length=self.hop_length,
        )
        time_in_seconds = np.arange(0, round(chromas_timing[-1]))
        detected_chromas_in_sec = np.round(
            np.interp(time_in_seconds, chromas_timing, highest_prob_pitchs)
        )
        detected_chromas = [ChromaIndex(pitch) for pitch in detected_chromas_in_sec]
        return detected_chromas


class AudioProcessor:
    def __init__(
        self,
        audio_format: Optional[AudioFormat] = None,
        bpm_detector: Optional[BPMDetector] = None,
        pitch_detector: Optional[PitchDetector] = None,
    ) -> None:
        """
        The audio processor class is meant to process audio samples and detect features
        like BPM and pitch. It uses the provided detectors to detect the features.
        """
        if bpm_detector is None and pitch_detector is None:
            raise ValueError("At least one detector must be provided.")

        self.audio_format = audio_format
        self.bpm_detector = bpm_detector
        self.pitch_detector = pitch_detector

    def set_sampling_rate(self, sampling_rate: float) -> None:
        """
        Both detectors need to have the same sampling rate of the audio samples to
        perform the analysis. This method sets the sampling rate for both detectors.
        """
        if self.bpm_detector is not None:
            self.bpm_detector.sampling_rate = sampling_rate
        if self.pitch_detector is not None:
            self.pitch_detector.sampling_rate = sampling_rate

    async def process_audio_sample(self, audio_sample: np.ndarray) -> AudioSampleFeatures:
        """
        Process the audio sample and detect the features like BPM and pitch.
        """
        if self.audio_format is not None:
            audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        else:
            audio_sample_normalized = audio_sample

        # Detect BPM and pitch asynchronously
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
