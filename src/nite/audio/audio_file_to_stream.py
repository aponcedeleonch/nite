from pydub import AudioSegment
from pydub.playback import play
import pyaudio
import wave
import io

from nite.logging import configure_module_logging

logger = configure_module_logging("nite.audio_listener")


class AudioFileToStream:
    '''
    This class is responsible for converting an audio file to a stream.
    The input file is loaded into an AudioSegment and then converted into a stream.
    '''
    def __init__(self, file, format):
        self.input_song = file
        self.format = format


    def play(self):
        # Load the audio file into AudioSegment
        audio_segment = AudioSegment.from_file(self.input_song, format=self.format)

        # Convert the AudioSegment into a stream
        audio_stream = io.BytesIO()
        audio_segment.export(audio_stream, format="wav")
        audio_stream.seek(0)

        # Play the stream
        play(AudioSegment.from_file(audio_stream, format="wav"))

        # Close the stream
        audio_stream.close()




class AudioFileToStreamPyAudio:
    '''
    This class is responsible for converting an audio file in wav format to a stream using PyAudio.
    '''
    def __init__(self, file, chunk=1024):
        self.chunk = chunk
        self.input_file = wave.open(file, 'rb')
        self.pyaud = pyaudio.PyAudio()
        self.stream = self.pyaud.open(
                                      format=self.pyaud.get_format_from_width(self.input_file.getsampwidth()),
                                      channels=self.input_file.getnchannels(),
                                      rate=self.input_file.getframerate(),
                                      output = True
                                      )

    def play(self):
        """ Play entire file """
        data = self.input_file.readframes(self.chunk)
        while data:
            self.stream.write(data)
            data = self.input_file.readframes(self.chunk)

        self.stream.close()
        self.pyaud.terminate()

