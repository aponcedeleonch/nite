from typing import Optional, Dict, Any
from pathlib import Path

from .elements import NiteEnvironment, ColorRgb, OrbitPoint, PointOrDirection, ParticleSysytem
from .constants import (
    ORBITPOINT_NAME, VELOCITY_NAME, COLOR_NAME, SHAPE_NAME, NUMBER_OF_PARTICLES_NAME, KILL_OLD_NAME
)
from .config import NUMBER_OF_MIDIS, DEFAULT_ENVIRONMENT_NAME


class NiteEnvironmentOps:

    def __init__(self) -> None:
        self.nite_env = NiteEnvironment()

    def _save_env_to_file(self) -> None:
        print(self.nite_env)

    def load_from_file(self, saved_env: Optional[str] = None) -> None:
        if not saved_env:
            return self.nite_env

        saved_env = f'{saved_env}.pd'
        filepath = Path() / 'saved_environments' / saved_env
        if not filepath.is_file():
            raise FileNotFoundError(f"Nite Envioronment not found: {filepath}")

        # TODO: Load logic here

    def _parse_point_or_direction(self, nite_env: Dict[str, Any], base_name: str, point_or_direction_i: int) -> PointOrDirection:
        point_or_direction = PointOrDirection(
                                            x=nite_env.get(f'{base_name}-{point_or_direction_i}-x') or None,
                                            y=nite_env.get(f'{base_name}-{point_or_direction_i}-y') or None,
                                            z=nite_env.get(f'{base_name}-{point_or_direction_i}-z') or None,
                                        )
        return point_or_direction

    def _parse_color(self, nite_env: Dict[str, Any], color_i: int) -> ColorRgb:
        color = ColorRgb(
                        r=nite_env.get(f'{COLOR_NAME}-{color_i}-r') or None,
                        g=nite_env.get(f'{COLOR_NAME}-{color_i}-g') or None,
                        b=nite_env.get(f'{COLOR_NAME}-{color_i}-b') or None,
                    )
        return color

    def _parse_orbit_point(self, nite_env: Dict[str, Any], orbit_point_i: int) -> OrbitPoint:
        orbit_point = OrbitPoint(
                                point=self._parse_point_or_direction(nite_env, ORBITPOINT_NAME, orbit_point_i),
                                force=nite_env.get(f'{ORBITPOINT_NAME}-{orbit_point_i}-force') or None
                            )
        return orbit_point

    def _parse_velocity(self, nite_env: Dict[str, Any], velocity_i: int) -> PointOrDirection:
        velocity = self._parse_point_or_direction(nite_env, VELOCITY_NAME, velocity_i)
        return velocity

    def _parse_particle_system(self, nite_env: Dict[str, Any], midi_i: int) -> ParticleSysytem:
        particle_system = ParticleSysytem(
                                        shape=nite_env.get(f'{SHAPE_NAME}-{midi_i}') or None,
                                        color_rgb=self._parse_color(nite_env, midi_i),
                                        number_of_particles=nite_env.get(f'{NUMBER_OF_PARTICLES_NAME}-{midi_i}') or None,
                                        orbitpoint=self._parse_orbit_point(nite_env, midi_i),
                                        velocity=self._parse_velocity(nite_env, midi_i),
                                        killold=nite_env.get(f'{KILL_OLD_NAME}-{midi_i}') or None
                                    )
        return particle_system

    def save_form_dict(self, nite_env: Dict[str, Any]) -> NiteEnvironment:
        midis = []
        for i in range(NUMBER_OF_MIDIS):
            midi_i = i + 1
            midis.append(self._parse_particle_system(nite_env, midi_i))
        self.nite_env = NiteEnvironment(name=nite_env.get('name') or DEFAULT_ENVIRONMENT_NAME, midis=midis)
        self._save_env_to_file()
        return self.nite_env
