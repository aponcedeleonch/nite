import numpy as np
import pytest

from nite.audio import audio_action


@pytest.mark.parametrize("bpm,expected_duration", [(120, 2), (0, np.inf), (None, np.inf)])
def test_calculate_bar_duration_seconds(bpm: float, expected_duration: float):
    beats_per_compass: int = 4
    bpm_action = audio_action.AudioActionBPM(
        bpm_action_frequency=audio_action.BPMActionFrequency.kick,
        beats_per_compass=beats_per_compass,
    )
    result_duration = bpm_action._calculate_bar_duration_seconds(bpm, beats_per_compass)
    assert result_duration == expected_duration


@pytest.mark.parametrize(
    "bar_duration_sec,bpm_action_frequency,expected_action_period",
    [
        (np.inf, audio_action.BPMActionFrequency.kick, np.inf),
        (0, audio_action.BPMActionFrequency.kick, 0),
        (4, audio_action.BPMActionFrequency.kick, 1),
        (4, audio_action.BPMActionFrequency.compass, 4),
        (4, audio_action.BPMActionFrequency.two_compass, 8),
        (4, audio_action.BPMActionFrequency.four_compass, 16),
    ],
)
def test_calculate_action_period(
    bar_duration_sec: float,
    bpm_action_frequency: audio_action.BPMActionFrequency,
    expected_action_period: float,
):
    beats_per_compass: int = 4
    bpm_action = audio_action.AudioActionBPM(
        bpm_action_frequency=audio_action.BPMActionFrequency.kick,
        beats_per_compass=beats_per_compass,
    )
    result_action_period = bpm_action._calculate_action_period(
        bar_duration_sec, bpm_action_frequency, beats_per_compass
    )
    assert result_action_period == expected_action_period


@pytest.mark.parametrize(
    "bpm,bpm_action_frequency,expected_period_timeout",
    [
        (None, audio_action.BPMActionFrequency.kick, np.inf),
        (0, audio_action.BPMActionFrequency.kick, np.inf),
        (120, audio_action.BPMActionFrequency.kick, 0.5),
        (120, audio_action.BPMActionFrequency.compass, 2),
        (120, audio_action.BPMActionFrequency.two_compass, 4),
        (120, audio_action.BPMActionFrequency.four_compass, 8),
    ],
)
def test_calculate_period_timeout_sec(
    bpm: float,
    bpm_action_frequency: audio_action.BPMActionFrequency,
    expected_period_timeout: float,
):
    beats_per_compass: int = 4
    bpm_action = audio_action.AudioActionBPM(
        bpm_action_frequency=bpm_action_frequency, beats_per_compass=beats_per_compass
    )
    result_period_timeout = bpm_action._calculate_period_timeout_sec(bpm)
    assert result_period_timeout == expected_period_timeout


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bpm,time_since_last_timeout_ms,action_period_timeout_sec,time_in_ms,expected_should_act",
    [
        (None, 0, None, 10, False),
        (None, 10, np.inf, 1, False),
        (120, 2 * 1000, 2, 1, True),
    ],
)
async def test_bpm_act(
    bpm: float,
    time_since_last_timeout_ms: int,
    action_period_timeout_sec: float,
    time_in_ms: int,
    expected_should_act: bool,
):
    beats_per_compass: int = 4
    bpm_action = audio_action.AudioActionBPM(
        bpm_action_frequency=audio_action.BPMActionFrequency.kick,
        beats_per_compass=beats_per_compass,
    )
    bpm_action.bpm = bpm
    bpm_action.time_since_last_timeout_ms = time_since_last_timeout_ms
    bpm_action.action_period_timeout_sec = action_period_timeout_sec
    result_should_act = await bpm_action.act(time_in_ms)
    assert result_should_act is expected_should_act
