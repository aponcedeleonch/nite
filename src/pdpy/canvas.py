from typing import Dict

import networkx as nx

from pdpy.utils import clean_pd_str, transform_str_to_int
from pdpy.objects import PdObject, ObjBox, DeclareLib, pdobj_to_str, str_to_pdobj


class Canvas:

    def __init__(self, x=None, y=None, width=None, height=None, font_size=None):
        self.x = x or -100
        self.y = y or -100
        self.width = width or 400
        self.height = height or 400
        self.font_size = font_size or 12
        self.graph = nx.DiGraph()
        self.incremental_obj_id = 0

    def __str__(self):
        header_line = f"#N canvas {self.x} {self.y} {self.width} {self.height} {self.font_size};\n"
        added_libs = self._check_for_libs()
        obj_lines = self._transform_nodes_to_str()
        conn_lines = self._transform_edges_to_str()
        return header_line + added_libs + obj_lines + conn_lines

    def _check_for_libs(self) -> str:
        added_libs = []
        for obj_id, obj_data in self.graph.nodes(data=True):
            pdobj = self._get_pdobj_from_node(obj_data)
            if not isinstance(pdobj, ObjBox):
                continue
            
            if not 'declare' in pdobj.obj_args:
                continue

            lib_name = pdobj.obj_args[-1]
            lib_obj = DeclareLib(lib_name=lib_name)
            added_libs.append(str(lib_obj))

        return ''.join(added_libs)

    def _process_canvas_line(self, line: str) -> None:
        line = clean_pd_str(line)
        canvas_args = line.split('#N canvas ')[1]
        self.x, self.y, self.width, self.height, self.font_size = canvas_args.split(' ')

    def _process_connection_line(self, line: str):
        line = clean_pd_str(line)
        connection_list = line.split(' ')[2:]
        for i in range(len(connection_list)):
            connection_list[i] = transform_str_to_int(connection_list[i])
        connection_dict = {
            'src_obj_id': connection_list[0],
            'src_inlet': connection_list[1],
            'dst_obj_id': connection_list[2],
            'dst_inlet': connection_list[3]
        }

        self.add_connection(**connection_dict)

    def _process_object_line(self, line: str) -> None:
        obj_type_str = line.split(' ')[1]
        obj_class = str_to_pdobj.get(obj_type_str, None)
        if not obj_class:
            raise ValueError(f"Invalid object type: {obj_type_str}")
        obj = obj_class()
        obj.read_line(line)
        self.add_object(obj)

    def _get_pdobj_from_node(self, obj_node: Dict) -> PdObject:
        obj_type_str = obj_node.get('pdobj', None)
        if not obj_type_str:
            raise ValueError(f"Object type not found for node {obj_id}")

        obj_class = str_to_pdobj.get(obj_type_str, None)
        if not obj_class:
            raise ValueError(f"Invalid object type: {obj_type_str}")

        obj_kwargs = {arg: value for arg, value in obj_node.items() if arg != 'pdobj'}
        obj = obj_class(**obj_kwargs)
        return obj

    def _transform_nodes_to_str(self) -> str:
        list_nodes_str = []
        for obj_id in range(self.incremental_obj_id):
            obj_node = self.graph.nodes[obj_id]
            obj = self._get_pdobj_from_node(obj_node)
            list_nodes_str.append(str(obj))
        return ''.join(list_nodes_str)

    def _transform_edges_to_str(self) -> str:
        list_edges_str = []
        for src_obj_id, dst_obj_id, edge_data in self.graph.edges(data=True):
            src_inlet = edge_data['src_inlet']
            dst_inlet = edge_data['dst_inlet']
            list_edges_str.append(f"#X connect {src_obj_id} {src_inlet} {dst_obj_id} {dst_inlet};\n")
        return ''.join(list_edges_str)

    def add_connection(self, src_obj_id: int, dst_obj_id: int, src_inlet: int = 0, dst_inlet: int = 0):
        if src_obj_id not in self.graph:
            raise ValueError(f"Invalid source object id: {src_obj_id}")

        if dst_obj_id not in self.graph:
            raise ValueError(f"Invalid destination object id: {dst_obj_id}")

        self.graph.add_edge(src_obj_id, dst_obj_id, src_inlet=src_inlet, dst_inlet=dst_inlet)

    def add_object(self, obj: PdObject) -> int:
        if not isinstance(obj, PdObject):
            raise TypeError(f"Object must be an instance of PdObject, not {type(obj)}")
        str_pdobj = pdobj_to_str[obj.__class__]
        self.graph.add_node(self.incremental_obj_id, pdobj=str_pdobj, **obj.__dict__)
        object_id = self.incremental_obj_id
        if isinstance(obj, PdObject):
            self.incremental_obj_id += 1
        return object_id

    def read_from_file(self, filename):
        with open(filename, 'r') as file:
            for line in file:
                if line.startswith('#N canvas'):
                    self._process_canvas_line(line)
                elif line.startswith('#X connect'):
                    self._process_connection_line(line)
                else:
                    self._process_object_line(line)

    def write_to_file(self, filename):
        with open(filename, 'w') as file:
            file.write(str(self))
