import sys
import struct
import time
from datetime import timedelta
from multiprocessing import Process, Queue

import pyaudio
import numpy as np

from nite.config import AUDIO_SAMPLING_RATE, TERMINATE_MESSAGE
from nite.video_mixer import short_format, AudioFormat, ProcessWithQueue
from nite.logging import LogggingProcessConfig, configure_module_logging


LOGGING_NAME = 'nite.audio_detecter'
logger = configure_module_logging(LOGGING_NAME)

# Need to still investigate what is CHANNELS.
CHANNELS = 1 if sys.platform == 'darwin' else 2


class AudioDetecter(ProcessWithQueue):

    def __init__(self, audio_format: AudioFormat, threshold: float, queue: Queue, logging_config: LogggingProcessConfig = None):
        super().__init__(queue=queue)
        self.audio_format = audio_format
        self.threshold = threshold
        self.logging_config = logging_config
        logger.info(f'Loaded audio detecter. Threshold: {self.threshold}. Format: {self.audio_format}')

    def _calculate_rms(self, audio_sample: np.ndarray) -> float:
        audio_sample_normalized = audio_sample * self.audio_format.normalization_factor
        audio_rms = np.sqrt(np.mean(audio_sample_normalized ** 2))
        return audio_rms

    def _process_audio_block(self, in_data, frame_count, time_info, status):
        audio_sample = np.array(struct.unpack(self.audio_format.unpack_format % frame_count, in_data))
        audio_rms = self._calculate_rms(audio_sample)
        self._do_action_on_threshold(audio_rms)
        return in_data, pyaudio.paContinue

    def _do_action_on_threshold(self, audio_rms: float):
        if audio_rms > self.threshold:
            logger.info('Threshold reached!')

    def start(self) -> None:
        paud = pyaudio.PyAudio()
        stream = paud.open(
                            format=short_format.pyaudio_format,
                            channels=CHANNELS,
                            rate=AUDIO_SAMPLING_RATE,
                            input=True,
                            stream_callback=self._process_audio_block
                        )

        logger.info('Starting audio listening')
        start_audio_time = time.time()
        last_logged_time = 0
        while stream.is_active():
            received_message = self.receive_from_queue()
            if self.should_terminate(received_message):
                break
            elapsed_time = time.time() - start_audio_time
            elapsed_seconds = int(elapsed_time)
            if elapsed_seconds % 10 == 0 and elapsed_seconds > 0 and elapsed_seconds != last_logged_time:
                logger.info(f'Keep-alive message audio. Elapsed time: {timedelta(seconds=elapsed_time)}')
                last_logged_time = elapsed_seconds  # Update the last logged time
        elapsed_audio_time = time.time() - start_audio_time

        stream.close()
        paud.terminate()
        logger.info(f'Recording stopped. Elapsed time: {timedelta(seconds=elapsed_audio_time)}')


def main():
    queue = Queue()
    audio = AudioDetecter(audio_format=short_format, threshold=0.1, queue=queue)
    audio_process = Process(target=audio.start)
    audio_process.start()

    time.sleep(2)
    queue.put(TERMINATE_MESSAGE)
    audio_process.join()


if __name__ == '__main__':
    main()
