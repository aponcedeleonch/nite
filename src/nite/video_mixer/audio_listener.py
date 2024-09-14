import struct
from typing import List
import concurrent.futures

import pyaudio
import numpy as np

from nite.config import AUDIO_SAMPLING_RATE, MAX_ACION_WORKERS, AUDIO_CHANNELS
from nite.logging import configure_module_logging
from nite.video_mixer import ProcessWithQueue, CommQueues, TimeRecorder
from nite.video_mixer.audio import AudioFormat
from nite.video_mixer.audio_action import AudioAction


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


if __name__ == '__main__':
    import time
    from multiprocessing import Queue, Process
    from nite.video_mixer.audio import short_format
    from nite.video_mixer import Message
    from nite.config import TERMINATE_MESSAGE
    from nite.video_mixer.audio_action import AudioActionBPM, BPMActionFrequency

    queue_to_audio = Queue()
    queue_from_audio = Queue()
    queues = CommQueues(in_queue=queue_to_audio, out_queue=queue_from_audio)
    audio_action_bpm = AudioActionBPM(BPMActionFrequency.kick)
    audio_listener = AudioListener(queues=queues, audio_actions=[audio_action_bpm], audio_format=short_format)
    audio_process = Process(target=audio_listener.start)
    audio_process.start()
    time.sleep(180)
    terminate_message = Message(content=TERMINATE_MESSAGE, content_type='message')
    queue_to_audio.put(terminate_message)
    audio_process.join()
