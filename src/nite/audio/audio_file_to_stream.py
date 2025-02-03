from pydub import AudioSegment
from pydub.playback import play
import pyaudio
import wave
import io

from nite.config import STREAM_CHUNK
from nite.logging import configure_module_logging

logger = configure_module_logging("nite.audio.audio_file_to_stream")


DEFAULT_CHUNK = 1024

class AudioFileToStream:
    '''
    This class is responsible for converting an audio file to a stream.
    The input file is loaded into an AudioSegment and then converted into a stream.
    '''
    def __init__(
            self,
            file_name: str,
            file_format: str
        ) -> None:
        self.input_song = file_name
        self.format = file_format


    def play_as_stream(self):
        try:
            logger.info(f"Playing the audio file: {self.input_song} with format: {self.format}")
            # Load the audio file into AudioSegment
            audio_segment = AudioSegment.from_file(self.input_song, format=self.format)

            # Convert the AudioSegment into a stream
            audio_stream = io.BytesIO()
            audio_segment.export(audio_stream, format="wav")
            audio_stream.seek(0)

            # Play the stream
            play(AudioSegment.from_file(audio_stream, format="wav"))

        except Exception as ex:
            logger.error(f"Error while playing the audio file: {ex}")
            audio_stream.close()

        finally:
            audio_stream.close()



class AudioWaveFileToStream:
    '''
    This class is responsible for converting an audio file in wav format to a stream using PyAudio.
    '''
    def __init__(
            self,
            file_name: str,
            chunk: int = STREAM_CHUNK
            ) -> None:
        self.chunk = chunk
        self.input_file = wave.open(file_name, 'rb')
        self.pyaud = pyaudio.PyAudio()
        self.stream = self.pyaud.open(
            format=self.pyaud.get_format_from_width(self.input_file.getsampwidth()),
            channels=self.input_file.getnchannels(),
            rate=self.input_file.getframerate(),
            output = True
        )
        logger.info(f"Initializing with audio file: {file_name} with chunk size: {self.chunk}")

    def play_as_stream(self):
        try:
            
            self._play_audio()
            data = self.input_file.readframes(self.chunk)
            while data:
                self.stream.write(data)
                data = self.input_file.readframes(self.chunk)

        except Exception as ex:
            logger.error(f"Error while playing the audio file: {ex}")

        finally:
            self.stream.close()
            self.pyaud.terminate()

