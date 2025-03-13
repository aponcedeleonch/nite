import pyaudio
import structlog
from pydantic import BaseModel, computed_field

logger = structlog.get_logger("nite.audio")


class AudioFormat(BaseModel):
    name: str
    pyaudio_format: int
    bits_per_sample: int
    unpack_format: str

    @computed_field  # type: ignore[misc]
    @property
    def max_value(self) -> int:
        return 2**self.bits_per_sample

    @computed_field  # type: ignore[misc]
    @property
    def normalization_factor(self) -> float:
        return 1 / self.max_value


short_format = AudioFormat(
    name="short",
    pyaudio_format=pyaudio.paInt16,
    bits_per_sample=16,
    unpack_format="%dh",
)
