import concurrent.futures
import struct
from typing import List

import librosa
import numpy as np
import pyaudio

from nite.config import AUDIO_SAMPLING_RATE, MAX_ACION_WORKERS, AUDIO_CHANNELS
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues, TimeRecorder
from nite.video_mixer.audio.audio import AudioFormat
from nite.video_mixer.audio.audio_action import AudioAction
from nite.video_mixer.audio.audio_processing import AudioProcessor


LOGGING_NAME = 'nite.audio_listener'
logger = configure_module_logging(LOGGING_NAME)


class AudioListener(ProcessWithQueue):

    def __init__(self, queues: CommQueues, audio_actions: List[AudioAction], audio_format: AudioFormat):
        super().__init__(queues=queues)
        self.time_recorder = TimeRecorder()
        self.audio_format = audio_format
        self.audio_actions = audio_actions
        logger.info(f'Loaded audio listener. Format: {self.audio_format}')

    def _get_results_of_audio_actions(self, audio_sample: np.ndarray) -> bool:
        audio_action_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ACION_WORKERS) as executor:
            future_to_action = [executor.submit(action.act, audio_sample) for action in self.audio_actions]
            for future in concurrent.futures.as_completed(future_to_action):
                try:
                    audio_action_results.append(future.result())
                except Exception:
                    logger.exception('Audio action generated an exception')
        return any(audio_action_results)

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        audio_sample = np.array(struct.unpack(self.audio_format.unpack_format % frame_count, in_data))
        should_do_action = self._get_results_of_audio_actions(audio_sample)
        if should_do_action:
            self.send_audio_sample(audio_sample)
        return in_data, pyaudio.paContinue

    def start(self) -> None:
        paud = pyaudio.PyAudio()
        stream = paud.open(
                            format=self.audio_format.pyaudio_format,
                            channels=AUDIO_CHANNELS,
                            rate=AUDIO_SAMPLING_RATE,
                            input=True,
                            stream_callback=self._process_audio_block
                        )

        logger.info('Starting audio listening')
        self.time_recorder.start_recording_if_not_started()
        while stream.is_active():
            should_terminate, _ = self.receive()
            if should_terminate:
                break

            if self.time_recorder.has_period_passed:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

        stream.close()
        paud.terminate()
        logger.info(f'Audio listening stopped. Elapsed time: {self.time_recorder.elapsed_time_str}')


class AudioAnalyzer:

    def __init__(self, audio_processor: AudioProcessor) -> None:
        self.audio_processor = audio_processor

    async def analyze_song(self, song_path: str) -> None:
        audio_sample, sampling_rate = librosa.load(song_path)
        self.audio_processor.set_sampling_rate(sampling_rate)
        audio_features = await self.audio_processor.process_audio_sample(audio_sample)
        return audio_features
