from pydantic import BaseModel, computed_field
import pyaudio

from nite.logging import configure_module_logging

LOGGING_NAME = 'nite.audio'
logger = configure_module_logging(LOGGING_NAME)


class AudioFormat(BaseModel):
    name: str
    pyaudio_format: int
    bits_per_sample: int
    unpack_format: str

    @property
    @computed_field
    def max_value(self) -> int:
        return 2 ** self.bits_per_sample

    @property
    @computed_field
    def normalization_factor(self) -> float:
        return 1 / self.max_value


short_format = AudioFormat(name='short', pyaudio_format=pyaudio.paInt16, bits_per_sample=16, unpack_format='%dh')
