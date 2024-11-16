import numpy as np
import pytest

from nite.config import AUDIO_SAMPLING_RATE
from nite.video_mixer.buffers import TimedSampleBuffer, SampleBuffer


class MockTimeRecorder:
    def __init__(self, period_timeout_sec):
        self.period_timeout_sec = period_timeout_sec
        self.started = False
        self.period_passed = False

    def start_recording_if_not_started(self):
        self.started = True

    @property
    def has_period_passed(self):
        return self.period_passed

    def simulate_period_passed(self):
        self.period_passed = True


def test_initial_state():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    assert timed_sample_buffer.buffer.shape == (AUDIO_SAMPLING_RATE, 1)
    assert len(timed_sample_buffer.num_samples_per_second) == 1
    assert timed_sample_buffer.num_samples_per_second[0] == 0


def test_reset_buffer():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample = np.ones(AUDIO_SAMPLING_RATE // 2)
    timed_sample_buffer.add_sample_to_buffer(sample)

    timed_sample_buffer.reset_buffer()

    assert timed_sample_buffer.buffer.shape == (AUDIO_SAMPLING_RATE, 1)
    assert len(timed_sample_buffer.num_samples_per_second) == 1
    assert timed_sample_buffer.num_samples_per_second[0] == 0
    assert np.allclose(timed_sample_buffer(), 0)


def test_add_sample_to_buffer():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample = np.ones(AUDIO_SAMPLING_RATE // 2)
    timed_sample_buffer.add_sample_to_buffer(sample)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample), -1], sample)
    assert np.array_equal(timed_sample_buffer(), sample)


def test_add_two_samples_same_second():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample_1 = np.ones(10)
    timed_sample_buffer.add_sample_to_buffer(sample_1)
    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample_1)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample_1), -1], sample_1)
    assert np.array_equal(timed_sample_buffer(), sample_1)

    sample_2 = np.ones(20)
    timed_sample_buffer.add_sample_to_buffer(sample_2)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample_1) + len(sample_2)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample_1), -1], sample_1)
    assert np.array_equal(timed_sample_buffer.buffer[len(sample_1):len(sample_1) + len(sample_2), -1], sample_2)
    assert np.array_equal(timed_sample_buffer(), np.concatenate([sample_1, sample_2]))


def test_overflow_buffer():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=1, min_seconds_in_buffer=0, buffer_cap_per_sec=10)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample = np.ones(10)
    timed_sample_buffer.add_sample_to_buffer(sample)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample), -1], sample)
    assert np.array_equal(timed_sample_buffer(), sample)

    sample_overflow = np.ones(10) + 1
    timed_sample_buffer.add_sample_to_buffer(sample_overflow)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample), -1], sample)
    assert np.array_equal(timed_sample_buffer(), sample)


def test_add_sample_to_buffer_with_period_passed_and_empty_first_second():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)
    timed_sample_buffer.timer_buffer.simulate_period_passed()

    sample = np.ones(AUDIO_SAMPLING_RATE // 2)
    timed_sample_buffer.add_sample_to_buffer(sample)

    assert len(timed_sample_buffer.num_samples_per_second) == 2

    assert np.allclose(timed_sample_buffer.buffer[:, 0], 0)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample), -1], sample)
    assert np.array_equal(timed_sample_buffer(), sample)


def test_add_sample_to_buffer_with_period_passed():
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=5)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample_1 = np.ones(10)
    timed_sample_buffer.add_sample_to_buffer(sample_1)
    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample_1)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample_1), -1], sample_1)
    assert np.array_equal(timed_sample_buffer(), sample_1)

    timed_sample_buffer.timer_buffer.simulate_period_passed()

    sample_2 = np.ones(20)
    timed_sample_buffer.add_sample_to_buffer(sample_2)

    assert len(timed_sample_buffer.num_samples_per_second) == 2

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample_2)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample_2), -1], sample_2)

    assert np.array_equal(timed_sample_buffer(), np.concatenate([sample_1, sample_2]))


@pytest.mark.parametrize('min_seconds_in_buffer', [0, 1, 10])
def test_has_enough_data(min_seconds_in_buffer):
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=10, min_seconds_in_buffer=min_seconds_in_buffer)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    assert not timed_sample_buffer.has_enough_data()

    sample = np.ones(AUDIO_SAMPLING_RATE // 2)
    timed_sample_buffer.add_sample_to_buffer(sample)

    if min_seconds_in_buffer != 0:
        assert not timed_sample_buffer.has_enough_data()

    for _ in range(min_seconds_in_buffer + 1):
        timed_sample_buffer.timer_buffer.simulate_period_passed()
        sample = np.ones(AUDIO_SAMPLING_RATE // 2)
        timed_sample_buffer.add_sample_to_buffer(sample)

    assert timed_sample_buffer.has_enough_data()


@pytest.mark.parametrize('max_seconds_in_buffer', [1, 10])
def test_rotate_buffer(max_seconds_in_buffer):
    timed_sample_buffer = TimedSampleBuffer(max_seconds_in_buffer=max_seconds_in_buffer, min_seconds_in_buffer=0)
    timed_sample_buffer.timer_buffer = MockTimeRecorder(period_timeout_sec=1)

    sample_len = AUDIO_SAMPLING_RATE // 2
    sample = np.ones(sample_len)
    timed_sample_buffer.add_sample_to_buffer(sample)

    assert timed_sample_buffer.num_samples_per_second[-1] == len(sample)
    assert np.array_equal(timed_sample_buffer.buffer[:len(sample), -1], sample)
    assert np.array_equal(timed_sample_buffer(), sample)

    for i_sec in range(max_seconds_in_buffer + 1):
        timed_sample_buffer.timer_buffer.simulate_period_passed()
        sample = np.ones(sample_len) + (i_sec + 1)
        timed_sample_buffer.add_sample_to_buffer(sample)

    assert len(timed_sample_buffer.num_samples_per_second) == max_seconds_in_buffer + 1
    assert timed_sample_buffer.buffer.shape == (AUDIO_SAMPLING_RATE, max_seconds_in_buffer + 1)
    assert np.array_equal(timed_sample_buffer.buffer[:sample_len, 0], np.ones(sample_len) + 1)
    assert np.array_equal(timed_sample_buffer.buffer[:sample_len, -1], np.ones(sample_len) + max_seconds_in_buffer + 1)


@pytest.fixture
def sample_buffer():
    return SampleBuffer(max_buffer_size=10, min_buffer_size=5)


def test_initial_state_sample_buffer(sample_buffer):
    assert sample_buffer.buffer.shape == (0,)
    assert sample_buffer.max_buffer_size == 10
    assert sample_buffer.min_buffer_size == 5


def test_invalid_min_buffer_size():
    with pytest.raises(ValueError, match='min_buffer_size must be greater than 0'):
        SampleBuffer(max_buffer_size=10, min_buffer_size=0)


def test_invalid_max_buffer_size():
    with pytest.raises(ValueError, match='max_buffer_size must be equal or greater than min_buffer_size'):
        SampleBuffer(max_buffer_size=4, min_buffer_size=5)


def test_add_sample_to_sample_buffer(sample_buffer):
    sample = np.ones(3)  # Add 3 samples
    sample_buffer.add_sample_to_buffer(sample)

    assert np.array_equal(sample_buffer.buffer, sample)


def test_add_sample_and_rotate_buffer(sample_buffer):
    sample = np.ones(3)  # Add 3 samples
    for _ in range(4):  # Add samples to exceed max_buffer_size
        sample_buffer.add_sample_to_buffer(sample)

    assert sample_buffer.buffer.shape == (10,)
    assert np.array_equal(sample_buffer.buffer, np.ones(10))


def test_has_enough_data_sample_buffer(sample_buffer):
    assert not sample_buffer.has_enough_data()

    sample = np.ones(3)  # Add 3 samples
    for _ in range(2):  # Add samples to reach min_buffer_size
        sample_buffer.add_sample_to_buffer(sample)

    assert sample_buffer.has_enough_data()


def test_reset_buffer_sample_buffer(sample_buffer):
    sample = np.ones(3)  # Add 3 samples
    sample_buffer.add_sample_to_buffer(sample)
    sample_buffer.reset_buffer()

    assert sample_buffer.buffer.shape == (0,)


def test_call(sample_buffer):
    sample = np.ones(3)  # Add 3 samples
    sample_buffer.add_sample_to_buffer(sample)

    assert np.array_equal(sample_buffer(), sample)
