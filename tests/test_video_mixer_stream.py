import asyncio
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from nite.audio.audio_action import BPMActionFrequency
from nite.audio.audio_file_to_stream import AudioWaveFileToStream
from nite.video_mixer.factories import VideoCombinerFactory

PROJECT_DIR = Path(__file__).parent




class TestVideoMixerStream(TestCase):
    def setUp(self):
        self.video_factory = VideoCombinerFactory(
        video_1=_get_file_path("GG-ANIMATED_3.mp4"),
        video_2=_get_file_path("GG-ANIMATED_7.mp4"),
        alpha=_get_file_path("ALPHA1.mp4"),
        width=640,
        height=360,
        bpm_frequency=BPMActionFrequency.kick,
        min_pitch=0,
        max_pitch=11,
        blend_operation="darken",
        blend_falloff=0.5,
        playback_time_sec=10,
    )

    def _audio_lister_side_effect(self):
        audio_wav_file_stream = AudioWaveFileToStream(file_name=_get_file_path("Arden_Kres-Nite_V2.wav"),
                                                      audio_listener=self.video_factory.audio_listener)
        audio_wav_file_stream.play_as_stream()

    @patch("nite.audio.audio_io.AudioListener.start")
    def test_video_mixer_stream(self, mock_audio_listener):
        video_combiner = asyncio.run(self.video_factory.get_stream_config())
        mock_audio_listener.side_effect = self._audio_lister_side_effect
        video_combiner.stream()

def _get_file_path(file_name: str) -> str:
    return str(Path(PROJECT_DIR)/file_name)