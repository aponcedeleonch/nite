from typing import Optional, List

from pydantic import BaseModel

from .config import NUMBER_OF_MIDIS, DEFAULT_ENVIRONMENT_NAME


class ColorRgb(BaseModel):
    r: Optional[float] = None
    g: Optional[float] = None
    b: Optional[float] = None


class PointOrDirection(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


class OrbitPoint(BaseModel):
    point: PointOrDirection = PointOrDirection()
    force: Optional[float] = None


class ParticleSysytem(BaseModel):
    shape: Optional[str] = None
    color_rgb: ColorRgb = ColorRgb()
    number_of_particles: Optional[int] = None
    orbitpoint: OrbitPoint = OrbitPoint()
    velocity: PointOrDirection = PointOrDirection()
    killold: Optional[int] = None


class NiteEnvironment(BaseModel):
    name: str = DEFAULT_ENVIRONMENT_NAME
    midis: List[ParticleSysytem] = [ParticleSysytem() for _ in range(NUMBER_OF_MIDIS)]
