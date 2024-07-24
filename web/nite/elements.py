from typing import Optional, List

from pydantic import BaseModel


class ColorRgb(BaseModel):
    r: float
    g: float
    b: float


class PointOrDirection(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class OrbitPoint(BaseModel):
    point: PointOrDirection
    force: float


class ParticleSysytem(BaseModel):
    shape: Optional[str] = None
    color_rgb: Optional[ColorRgb] = None
    number_of_particles: Optional[int] = None
    orbitpoint: Optional[OrbitPoint] = None
    velocity: Optional[PointOrDirection] = None
    killold: Optional[int] = None


class NiteEnvironment(BaseModel):
    name: str = 'New Nite Environment'
    midis: List[ParticleSysytem] = [ParticleSysytem(), ParticleSysytem(), ParticleSysytem(), ParticleSysytem()]
