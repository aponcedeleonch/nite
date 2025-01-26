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


class BPMActionFrequency(int, Enum):
    kick = 0
    compass = 1
    two_compass = 2
    four_compass = 4


class AudioAction(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def act(self, time_in_ms: int) -> Tuple[bool, float]:
        pass


class AudioActionBPM(AudioAction):
    def __init__(
        self,
        bpm_action_frequency: BPMActionFrequency,
        beats_per_compass: int = 4,
    ) -> None:
        super().__init__()
        self.beats_per_compass = beats_per_compass
        self.bpm_action_frequency = bpm_action_frequency
        logger.info(f"Beats per compass: {beats_per_compass}. Frequency: {bpm_action_frequency}. ")
        self.time_since_last_timeout_ms: int = 0
        self.bpm: Optional[float] = None
        self.action_period_timeout_sec: Optional[float] = None

    def set_bpm(self, bpm: float) -> None:
        self.bpm = bpm
        self.action_period_timeout_sec = self._calculate_period_timeout_sec(bpm)

    def _calculate_bar_duration_seconds(self, bpm: float, beats_per_compass: int) -> float:
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
        if bpm_action_frequency == BPMActionFrequency.kick:
            return bar_duration_sec / beats_per_compass
        else:
            return bar_duration_sec * bpm_action_frequency

    def _calculate_period_timeout_sec(self, bpm: float) -> float:
        bar_duration_sec = self._calculate_bar_duration_seconds(bpm, self.beats_per_compass)
        return self._calculate_action_period(
            bar_duration_sec, self.bpm_action_frequency, self.beats_per_compass
        )

    async def act(self, time_in_ms: int) -> Tuple[bool, float]:
        self.time_since_last_timeout_ms += time_in_ms

        if self.bpm is None or self.action_period_timeout_sec is None:
            return False, 0.0

        time_since_last_timeout_sec = self.time_since_last_timeout_ms / 1000
        if time_since_last_timeout_sec >= self.action_period_timeout_sec:
            logger.info(
                f"BPM: {self.bpm}. "
                f"Action frequency: {self.bpm_action_frequency}. "
                f"Action period: {self.action_period_timeout_sec}."
            )
            offset_sec = time_since_last_timeout_sec - self.action_period_timeout_sec
            self.time_since_last_timeout_ms = int(offset_sec * 1000)
            return True, 1.0
        return False, 0.0


class AudioActionPitch(AudioAction):
    def __init__(self, min_pitch: ChromaIndex, max_pitch: ChromaIndex) -> None:
        super().__init__()
        if min_pitch >= max_pitch:
            raise ValueError("Min pitch must be less than max pitch")

        self.min_pitch = min_pitch
        self.max_pitch = max_pitch
        self.chromas: Optional[List[ChromaIndex]] = None
        self.total_time_in_ms = 0

    def set_pitches(self, chromas: List[ChromaIndex]) -> None:
        self.chromas = chromas

    async def act(self, time_in_ms: int) -> Tuple[bool, float]:
        self.total_time_in_ms += time_in_ms
        if self.chromas is None:
            return False, 0.0
        time_in_sec = int(round(self.total_time_in_ms / 1000))
        chroma_for_sec = self.chromas[time_in_sec]
        if self.min_pitch <= chroma_for_sec <= self.max_pitch:
            logger.info(
                f"Chroma: {chroma_for_sec} Min pitch: {self.min_pitch} Max pitch: {self.max_pitch}"
            )
            return True, 1.0
        return False, 0.0


class AudioActions(AudioAction):
    def __init__(self, audio_actions: List[AudioAction], blend_falloff_sec: float = 0) -> None:
        self.actions = audio_actions
        self.time_since_last_action_ms = np.inf
        self.blend_falloff_sec = blend_falloff_sec

    def set_features(self, audio_sample_features: AudioSampleFeatures) -> None:
        for action in self.actions:
            if isinstance(action, AudioActionBPM):
                if audio_sample_features.bpm is None:
                    raise InvalidAudioFeatureError("Cannnot set BPM to None")
                action.set_bpm(audio_sample_features.bpm)
            elif isinstance(action, AudioActionPitch):
                if audio_sample_features.pitches is None:
                    raise InvalidAudioFeatureError("Cannnot set pitches to None")
                action.set_pitches(audio_sample_features.pitches)

    async def act(self, time_in_ms: int) -> Tuple[bool, float]:
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for action in self.actions:
                tasks.append(tg.create_task(action.act(time_in_ms)))

        should_blend_per_action = [task.result()[0] for task in tasks]
        should_blend = any(should_blend_per_action)

        if should_blend:
            self.time_since_last_action_ms = 0
            blend_strength = 1.0
        else:
            self.time_since_last_action_ms += time_in_ms
            if self.blend_falloff_sec == 0:
                return False, 0.0
            blend_falloff_ms = self.blend_falloff_sec * 1000
            # Calculate blend strength based on blend_falloff_sec
            blend_strength = max(0.0, 1.0 - (self.time_since_last_action_ms / blend_falloff_ms))
            should_blend = blend_strength > 0.0

        return should_blend, blend_strength
