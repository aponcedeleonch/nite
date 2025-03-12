import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from nite.audio.audio_processing import AudioSampleFeatures, ChromaIndex
from nite.logging import configure_module_logging

logger = configure_module_logging("nite.audio_action")


class InvalidAudioFeatureError(Exception):
    pass


class InvalidPitchSecondError(Exception):
    pass


class BPMActionFrequency(int, Enum):
    kick = 0
    compass = 1
    two_compass = 2
    four_compass = 4


class AudioAction(ABC):
    @abstractmethod
    async def act(self, time_in_ms: int) -> bool:
        pass


class AudioActionBPM(AudioAction):
    def __init__(
        self,
        bpm_action_frequency: BPMActionFrequency,
        beats_per_compass: int = 4,
    ) -> None:
        """
        Given a BPM and a frequency of action, this class will trigger an action

        beats_per_compass: Number of beats per compass. Default is 4, i.e. 4/4 time signature.
        """
        self.beats_per_compass = beats_per_compass
        self.bpm_action_frequency = bpm_action_frequency
        logger.info(f"Beats per compass: {beats_per_compass}. Frequency: {bpm_action_frequency}. ")
        self.time_since_last_timeout_ms: int = 0
        self.bpm: Optional[float] = None
        self.action_period_timeout_sec: Optional[float] = None

    def set_bpm(self, bpm: float) -> None:
        """
        Set a new detected BPM from the audio processing.

        Every time the BPM is set, the action period timeout is recalculated.
        """
        self.bpm = bpm
        self.action_period_timeout_sec = self._calculate_period_timeout_sec(bpm)

    def _calculate_bar_duration_seconds(self, bpm: float, beats_per_compass: int) -> float:
        """
        Calculate the duration of a bar in seconds given the BPM and the number of beats per compass
        """
        # Handle the case bpm is None or 0
        if not bpm:
            # Return a very large number to:
            # 1. Avoid division by zero
            # 2. Avoid triggering actions
            return np.inf
        return beats_per_compass / bpm * 60

    def _calculate_action_period(
        self,
        bar_duration_sec: float,
        bpm_action_frequency: float,
        beats_per_compass: int,
    ) -> float:
        """
        Calculate the period of time in seconds between actions given the bar duration and
        the user configured action frequency.
        """
        if bpm_action_frequency == BPMActionFrequency.kick:
            return bar_duration_sec / beats_per_compass
        else:
            return bar_duration_sec * bpm_action_frequency

    def _calculate_period_timeout_sec(self, bpm: float) -> float:
        """
        Calculate the period of time in seconds between actions given the BPM and the user
        configured action frequency.
        """
        bar_duration_sec = self._calculate_bar_duration_seconds(bpm, self.beats_per_compass)
        return self._calculate_action_period(
            bar_duration_sec, self.bpm_action_frequency, self.beats_per_compass
        )

    async def act(self, time_in_ms: int) -> bool:
        """
        Check if the action period has passed and reset the time since last timeout.
        """
        self.time_since_last_timeout_ms += time_in_ms

        if self.bpm is None or self.action_period_timeout_sec is None:
            return False

        time_since_last_timeout_sec = self.time_since_last_timeout_ms / 1000
        if time_since_last_timeout_sec >= self.action_period_timeout_sec:
            logger.info(
                f"BPM: {self.bpm}. "
                f"Action frequency: {self.bpm_action_frequency}. "
                f"Action period: {self.action_period_timeout_sec}."
            )
            # Calculate the offset to avoid losing time and the error to be accumulated
            offset_sec = time_since_last_timeout_sec - self.action_period_timeout_sec
            self.time_since_last_timeout_ms = int(offset_sec * 1000)
            return True
        return False


class AudioActionPitch(AudioAction):
    def __init__(self, min_pitch: ChromaIndex, max_pitch: ChromaIndex) -> None:
        """
        Audio action that triggers when the pitch is within a certain range.

        TODO: This class needs more testing to ensure it works as expected.
        """
        if min_pitch >= max_pitch:
            raise InvalidAudioFeatureError("Min pitch must be less than max pitch")

        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.chromas: Optional[List[ChromaIndex]] = None
        self.total_time_in_ms = 0

    def set_pitches(self, chromas: List[ChromaIndex]) -> None:
        """
        Set new chromas detected from the audio processing.
        """
        self.chromas = chromas

    async def act(self, time_in_ms: int) -> bool:
        """
        Act based on the chroma detected from the audio processing.
        """

        self.total_time_in_ms += time_in_ms

        # Handle the case chromas is None
        if self.chromas is None:
            return False

        time_in_sec = int(round(self.total_time_in_ms / 1000))

        try:
            chroma_for_sec = self.chromas[time_in_sec]
        except IndexError:
            raise InvalidPitchSecondError(
                "Tried to select a second from the chromas we haven't calculated"
            )

        # Check if the chromas are within the range
        if self.min_pitch <= chroma_for_sec <= self.max_pitch:
            logger.info(
                f"Chroma: {chroma_for_sec} Min pitch: {self.min_pitch} Max pitch: {self.max_pitch}"
            )
            return True
        return False


class AudioActions(AudioAction):
    def __init__(self, audio_actions: List[AudioAction], blend_falloff_sec: float = 0) -> None:
        """
        Run multiple audio actions.
        """
        self.actions = audio_actions
        self.time_since_last_action_ms = np.inf
        self.blend_falloff_sec = blend_falloff_sec

    def set_features(self, audio_sample_features: AudioSampleFeatures) -> None:
        """
        Set the audio features for all the actions.
        """
        for action in self.actions:
            if isinstance(action, AudioActionBPM):
                if audio_sample_features.bpm is not None:
                    action.set_bpm(audio_sample_features.bpm)
            elif isinstance(action, AudioActionPitch):
                if audio_sample_features.pitches is not None:
                    action.set_pitches(audio_sample_features.pitches)

    async def act(self, time_in_ms: int) -> Tuple[bool, float]:
        """
        Act based on the audio features for all the actions.
        """
        # Run all the actions asynchronously
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for action in self.actions:
                tasks.append(tg.create_task(action.act(time_in_ms)))

        # Check if according to any action we should act (blend)
        should_blend_per_action = [task.result() for task in tasks]
        should_blend = any(should_blend_per_action)

        # If we should blend means the action just happened, so we reset the time since last action
        # and the blend strength is 1.0
        if should_blend:
            self.time_since_last_action_ms = 0
            blend_strength = 1.0
        else:
            # If we shouldn't blend, we calculate the blend strength based on the blend falloff
            self.time_since_last_action_ms += time_in_ms

            # There is no faloff time, we can finish here
            if self.blend_falloff_sec == 0:
                return False, 0.0

            # Calculate blend strength based on blend_falloff_sec
            blend_falloff_ms = self.blend_falloff_sec * 1000
            blend_strength = max(0.0, 1.0 - (self.time_since_last_action_ms / blend_falloff_ms))
            should_blend = blend_strength > 0.0

        return should_blend, blend_strength
