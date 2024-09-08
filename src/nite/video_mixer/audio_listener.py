import sys
import struct
from typing import List
import concurrent.futures

import pyaudio
import numpy as np

from nite.config import AUDIO_SAMPLING_RATE, MAX_ACION_WORKERS
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues
from nite.video_mixer.audio import AudioFormat
from nite.video_mixer.audio_action import AudioAction


LOGGING_NAME = 'nite.audio_listener'
logger = configure_module_logging(LOGGING_NAME)

# Need to still investigate what is CHANNELS.
CHANNELS = 1 if sys.platform == 'darwin' else 2


class AudioListener(ProcessWithQueue):

    def __init__(self, queues: CommQueues, audio_actions: List[AudioAction], audio_format: AudioFormat):
        super().__init__(queues=queues)
        self.audio_format = audio_format
        self.audio_actions = audio_actions
        logger.info(f'Loaded audio listener. Format: {self.audio_format}')

    def _get_results_of_audio_actions(self, audio_sample: np.ndarray) -> bool:
        audio_action_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ACION_WORKERS) as executor:
            future_to_action = [executor.submit(action.process, audio_sample) for action in self.audio_actions]
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
                            channels=CHANNELS,
                            rate=AUDIO_SAMPLING_RATE,
                            input=True,
                            stream_callback=self._process_audio_block
                        )

        logger.info('Starting audio listening')
        while stream.is_active():
            should_terminate, _ = self.receive()
            if should_terminate:
                break

            if self.time_recorder.has_period_passed:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

        stream.close()
        paud.terminate()
        logger.info(f'Audio listening stopped. Elapsed time: {self.time_recorder.elapsed_time_str}')
