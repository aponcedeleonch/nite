import sys
import struct
import time
from multiprocessing import Process, Queue

import pyaudio
import numpy as np

from nite.config import AUDIO_SAMPLING_RATE, TERMINATE_MESSAGE
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues
from nite.video_mixer.audio import AudioFormat, short_format


LOGGING_NAME = 'nite.audio_detecter'
logger = configure_module_logging(LOGGING_NAME)

# Need to still investigate what is CHANNELS.
CHANNELS = 1 if sys.platform == 'darwin' else 2


class AudioDetecter(ProcessWithQueue):

    def __init__(self, threshold: float, queues: CommQueues, audio_format: AudioFormat = short_format):
        super().__init__(queues=queues)
        self.audio_format = audio_format
        self.threshold = threshold
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
            self.send_message(f'Audio detected. RMS: {audio_rms}')

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
            message = self.receive_message()
            if self.should_terminate(message):
                break

            if self.time_recorder.should_send_keepalive:
                logger.info(f'Keep-alive. Elapsed time: {self.time_recorder.elapsed_time_str}')

        stream.close()
        paud.terminate()
        logger.info(f'Recording stopped. Elapsed time: {self.time_recorder.elapsed_time_str}')


def main():
    queue = Queue()
    audio = AudioDetecter(threshold=0.1, queue=queue)
    audio_process = Process(target=audio.start)
    audio_process.start()

    time.sleep(15)
    terminate_msg = f'{{ "sender": "main", "receiver": "audio_detecter", "message": "{TERMINATE_MESSAGE}" }}'
    queue.put(terminate_msg)
    audio_process.join()


if __name__ == '__main__':
    main()
