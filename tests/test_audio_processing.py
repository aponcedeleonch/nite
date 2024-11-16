import numpy as np
import pytest
import librosa

from nite.config import (
    AUDIO_SAMPLING_RATE, BPM_BUFFER_SECONDS_MIN, BPM_BUFFER_SECONDS_MAX, BPM_BUFFER_BPMS_MIN, BPM_BUFFER_BPMS_MAX,
    BPM_BUFFER_SECS_REMOVE
)
from nite.video_mixer.audio.audio_processing import BPMDetector, PitchDetector, ChromaIndex
from nite.video_mixer.buffers import SampleBuffer


class MockBuffer:
    def __init__(self, has_enough_data: bool = True):
        self.data = []
        self.has_enough_data_flag = has_enough_data

    def add_sample_to_buffer(self, sample):
        self.data.append(sample)

    def reset_buffer(self):
        self.data = []

    def has_enough_data(self):
        return self.has_enough_data_flag

    def __call__(self):
        return np.array(self.data).reshape(-1)


@pytest.fixture
def bpm_detecter():
    buffer_audio = MockBuffer(has_enough_data=True)
    buffer_recorded_bpms = MockBuffer(has_enough_data=True)
    return BPMDetector(buffer_audio=buffer_audio, buffer_recorded_bpms=buffer_recorded_bpms)


def test_initial_state(bpm_detecter: BPMDetector):
    assert bpm_detecter.tolerance_threshold == 10
    assert isinstance(bpm_detecter.buffer_audio, MockBuffer)
    assert isinstance(bpm_detecter.buffer_recorded_bpms, MockBuffer)


@pytest.mark.parametrize('has_enough_data', [True, False])
def test_has_bpm_changed_significantly(bpm_detecter: BPMDetector, has_enough_data: bool):
    bpm_detecter.buffer_recorded_bpms.has_enough_data_flag = has_enough_data

    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(100)
    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(105)
    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(110)

    if not has_enough_data:
        assert not bpm_detecter._has_bpm_changed_significantly(120)
    else:
        assert bpm_detecter._has_bpm_changed_significantly(120)
        assert not bpm_detecter._has_bpm_changed_significantly(105)


@pytest.mark.parametrize('has_enough_data', [True, False])
def test_get_avg_recorded_bpms(bpm_detecter: BPMDetector, has_enough_data: bool):
    bpm_detecter.buffer_recorded_bpms.has_enough_data_flag = has_enough_data

    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(100)
    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(105)
    bpm_detecter.buffer_recorded_bpms.add_sample_to_buffer(110)

    if not has_enough_data:
        assert bpm_detecter._get_avg_recorded_bpms() is None
    else:
        assert bpm_detecter._get_avg_recorded_bpms() == 105


@pytest.mark.parametrize('has_enough_data', [True, False])
def test_get_estimated_bpm(bpm_detecter: BPMDetector, has_enough_data: bool):
    audio_sample = np.random.randn(AUDIO_SAMPLING_RATE)  # 1 second of random audio
    bpm_detecter.buffer_audio.add_sample_to_buffer(audio_sample)
    bpm_detecter.buffer_audio.has_enough_data_flag = has_enough_data

    if not has_enough_data:
        assert bpm_detecter._get_estimated_bpm() is None
    else:
        estimated_bpm = bpm_detecter._get_estimated_bpm()
        assert estimated_bpm is not None
        assert isinstance(estimated_bpm, np.ndarray)
        assert estimated_bpm.shape == (1,)


@pytest.mark.asyncio
async def test_detect_bpm(bpm_detecter: BPMDetector):
    audio_sample = np.random.randn(AUDIO_SAMPLING_RATE)  # 1 second of random audio

    detected_bpm = await bpm_detecter.detect(audio_sample)
    assert detected_bpm is not None
    assert isinstance(detected_bpm, float)


# The expected BPMs were obtained using the librosa.beat.beat_track function
# and making sure `beats` and `beats_cleaned` had the same value.
# _, audio_sample_percussive = librosa.effects.hpss(y)
# _, beats = librosa.beat.beat_track(y=y, sr=sr)
# _, beats_cleaned = librosa.beat.beat_track(y=audio_sample_percussive, sr=sr)
@pytest.mark.asyncio
@pytest.mark.parametrize('librosa_file, expected_bpm', [
    ('choice', 135.99),
    ('brahms', 151.99),
    ('pistachio', 143.55),
    ('fishin', 117.45),
    # ('nutcracker', 107.66),   # This track has very low BPM. For the moment skipping it. We can add it later
    # ('trumpet', 184.57),  # This track is 5.3 seconds. Too short for tests
    ('sweetwaltz', 151.99)
])
async def test_unmocked_detect_bpm(librosa_file: BPMDetector, expected_bpm: int):
    audio_array, sample_rate = librosa.load(librosa.ex(librosa_file))
    min_seconds, max_seconds = BPM_BUFFER_SECONDS_MIN, BPM_BUFFER_SECONDS_MAX
    min_bpms, max_bpms = BPM_BUFFER_BPMS_MIN, BPM_BUFFER_BPMS_MAX
    num_secs_remove = BPM_BUFFER_SECS_REMOVE
    buffer_audio = SampleBuffer(
                                min_buffer_size=min_seconds * sample_rate,
                                max_buffer_size=max_seconds * sample_rate,
                                num_samples_remove=num_secs_remove * sample_rate
                            )
    buffer_recorded_bpms = SampleBuffer(min_buffer_size=min_bpms, max_buffer_size=max_bpms)
    bpm_detecter = BPMDetector(buffer_audio=buffer_audio, buffer_recorded_bpms=buffer_recorded_bpms, sampling_rate=sample_rate)

    correct_bpm_detected = []
    for i in range(0, len(audio_array), sample_rate):
        audio_sample = audio_array[i:i + sample_rate]
        detected_bpm = await bpm_detecter.detect(audio_sample)
        if detected_bpm is not None:
            correct_bpm_detected.append(np.isclose(detected_bpm, expected_bpm, atol=1e-2))

    if len(correct_bpm_detected) == 0:
        avg_correct_bpm_detected = 0
    avg_correct_bpm_detected = np.mean(correct_bpm_detected)
    assert avg_correct_bpm_detected > 0.6


@pytest.fixture
def pitch_detector():
    buffer_audio = MockBuffer(has_enough_data=True)
    return PitchDetector(buffer_audio=buffer_audio, sampling_rate=AUDIO_SAMPLING_RATE)


def test_initial_state_pitch(pitch_detector: PitchDetector):
    assert pitch_detector.sampling_rate == AUDIO_SAMPLING_RATE
    assert isinstance(pitch_detector.buffer_audio, MockBuffer)


def test_get_latest_chromogram(pitch_detector: PitchDetector):
    audio_sample = np.random.randn(AUDIO_SAMPLING_RATE)  # 1 second of random audio
    pitch_detector.buffer_audio.add_sample_to_buffer(audio_sample)

    latest_chromogram = pitch_detector._get_chromogram()
    assert latest_chromogram is not None
    assert isinstance(latest_chromogram, np.ndarray)
    assert latest_chromogram.shape == (12,)


@pytest.mark.asyncio
async def test_detect_pitch(pitch_detector: PitchDetector):
    audio_sample = np.random.randn(AUDIO_SAMPLING_RATE)  # 1 second of random audio
    detected_pitch = await pitch_detector.detect(audio_sample)

    assert detected_pitch is not None
    assert isinstance(detected_pitch, ChromaIndex)


@pytest.mark.asyncio
async def test_detect_pitch_not_enough_data():
    buffer_audio = MockBuffer(has_enough_data=False)
    pitch_detector = PitchDetector(buffer_audio=buffer_audio, sampling_rate=AUDIO_SAMPLING_RATE)

    audio_sample = np.random.randn(AUDIO_SAMPLING_RATE)  # 1 second of random audio
    detected_pitch = await pitch_detector.detect(audio_sample)

    assert detected_pitch is None
