from pydantic import BaseModel, computed_field
import pyaudio


class AudioFormat(BaseModel):
    name: str
    pyaudio_format: int
    bits_per_sample: int
    unpack_format: str

    @computed_field
    @property
    def max_value(self) -> int:
        return 2 ** self.bits_per_sample

    @computed_field
    @property
    def normalization_factor(self) -> float:
        return 1 / self.max_value


short_format = AudioFormat(name='short', pyaudio_format=pyaudio.paInt16, bits_per_sample=16, unpack_format='%dh')
