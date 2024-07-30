from typing import Optional, Dict, Any
from pathlib import Path

from pdpy.canvas import Canvas
from pdpy.objects import DeclareLib, Message, ObjBox
from .elements import NiteEnvironment, ColorRgb, OrbitPoint, PointOrDirection, ParticleSysytem
from .constants import (
    ORBITPOINT_NAME, VELOCITY_NAME, COLOR_NAME, SHAPE_NAME, NUMBER_OF_PARTICLES_NAME, KILL_OLD_NAME
)
from .config import NUMBER_OF_MIDIS, DEFAULT_ENVIRONMENT_NAME, DEFAULT_SAVED_DIR


class NiteEnvParser:

    def __init__(self) -> None:
        pass

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

    def parse_form_dict(self, nite_env: Dict[str, Any]) -> NiteEnvironment:
        midis = []
        for i in range(NUMBER_OF_MIDIS):
            midi_i = i + 1
            midis.append(self._parse_particle_system(nite_env, midi_i))
        self.nite_env = NiteEnvironment(name=nite_env.get('name') or DEFAULT_ENVIRONMENT_NAME, midis=midis)
        return self.nite_env


class NiteEnvSaver:

    def __init__(self, nite_env: NiteEnvironment) -> None:
        self.nite_env = nite_env
        self.canvas = Canvas()
        self._create_gemwin_elems()
        self._create_particle_system(nite_env.midis[0])

    def _create_gemwin_elems(self) -> None:
        self.canvas.add_object(ObjBox(obj_args=['declare', '-lib', 'Gem']))
        create_id = self.canvas.add_object(Message(msg='create'))
        destroy_id = self.canvas.add_object(Message(msg='destroy'))
        toggle_id = self.canvas.add_object(ObjBox(obj_args=['tgl', '19', '0', 'empty', 'empty', 'empty', '0', '-10', '0', '12', '#fcfcfc', '#000000', '#000000', '0', '1']))
        gemwin_id = self.canvas.add_object(ObjBox(obj_args=['gemwin']))
        self.canvas.add_connection(src_obj_id=create_id, dst_obj_id=gemwin_id)
        self.canvas.add_connection(src_obj_id=destroy_id, dst_obj_id=gemwin_id)
        self.canvas.add_connection(src_obj_id=toggle_id, dst_obj_id=gemwin_id)
        dimen_id = self.canvas.add_object(Message(msg='dimen 800 600'))
        self.canvas.add_connection(src_obj_id=dimen_id, dst_obj_id=create_id)
        loadbang_id = self.canvas.add_object(ObjBox(obj_args=['loadbang']))
        self.canvas.add_connection(src_obj_id=loadbang_id, dst_obj_id=dimen_id)

    def _create_particle_system(self, particle_system: ParticleSysytem) -> None:
        draw_id = self.canvas.add_object(ObjBox(obj_args=['part_draw']))
        color_id = self.canvas.add_object(ObjBox(obj_args=['part_color', particle_system.color_rgb.r, particle_system.color_rgb.g, particle_system.color_rgb.b]))
        self.canvas.add_connection(src_obj_id=color_id, dst_obj_id=draw_id)

        orbit_id = self.canvas.add_object(ObjBox(obj_args=['part_orbitpoint', particle_system.orbitpoint.point.x, particle_system.orbitpoint.point.y, particle_system.orbitpoint.point.z, particle_system.orbitpoint.force]))
        self.canvas.add_connection(src_obj_id=orbit_id, dst_obj_id=color_id)
    
        killold_id = self.canvas.add_object(ObjBox(obj_args=['part_killold', particle_system.killold]))
        self.canvas.add_connection(src_obj_id=killold_id, dst_obj_id=orbit_id)

        velocity_id = self.canvas.add_object(ObjBox(obj_args=['part_velocity', particle_system.shape, particle_system.velocity.x, particle_system.velocity.y, particle_system.velocity.z]))
        self.canvas.add_connection(src_obj_id=velocity_id, dst_obj_id=killold_id)

        source_id = self.canvas.add_object(ObjBox(obj_args=['part_source', particle_system.number_of_particles]))
        self.canvas.add_connection(src_obj_id=source_id, dst_obj_id=velocity_id)

        head_id = self.canvas.add_object(ObjBox(obj_args=['part_head']))
        self.canvas.add_connection(src_obj_id=head_id, dst_obj_id=source_id)

        gemhead_id = self.canvas.add_object(ObjBox(obj_args=['gemhead']))
        self.canvas.add_connection(src_obj_id=gemhead_id, dst_obj_id=head_id)

    def save_to_file(self) -> None:
        folder_pathname = Path() / DEFAULT_SAVED_DIR
        folder_pathname.mkdir(exist_ok=True)
        file_pathname = folder_pathname / f'{self.nite_env.name}.pd'
        self.canvas.write_to_file(file_pathname)


class NiteEnvLoader:

    def __init__(self) -> None:
        self.nite_env = NiteEnvironment()

    def load_from_file(self, saved_env: Optional[str] = None) -> None:
        if not saved_env:
            return self.nite_env

        saved_env = f'{saved_env}.pd'
        filepath = Path() / 'saved_environments' / saved_env
        if not filepath.is_file():
            raise FileNotFoundError(f"Nite Envioronment not found: {filepath}")

        # TODO: Load logic here
