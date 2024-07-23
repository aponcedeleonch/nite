import networkx as nx

from pdpy.utils import clean_pd_str, transform_str_to_int
from pdpy.objects import PdObject, pdobj_to_str, str_to_pdobj


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
        obj_lines = self._transform_nodes_to_str()
        conn_lines = self._trnsform_edges_to_str()
        return header_line + obj_lines + conn_lines

    def _process_canvas_line(self, line: str) -> None:
        line = clean_pd_str(line)
        canvas_args = line.split('#N canvas ')[1]
        self.x, self.y, self.width, self.height, self.font_size = canvas_args.split(' ')

    def _process_connection_line(self, line: str):
        line = clean_pd_str(line)
        connection_list = line.split(' ')[2:]
        for i in range(len(connection_list)):
            connection_list[i] = transform_str_to_int(connection_list[i])

        self.add_connection(*connection_list)

    def _process_object_line(self, line: str) -> None:
        obj_type_str = line.split(' ')[1]
        obj_class = str_to_pdobj.get(obj_type_str, None)
        if not obj_class:
            raise ValueError(f"Invalid object type: {obj_type_str}")
        obj = obj_class()
        obj.read_line(line)
        self.add_object(obj)

    def _transform_nodes_to_str(self) -> str:
        list_nodes_str = []
        for obj_id in range(self.incremental_obj_id):
            obj_node = self.graph.nodes[obj_id]
            obj_type_str = obj_node.get('pdobj', None)
            if not obj_type_str:
                raise ValueError(f"Object type not found for node {obj_id}")

            obj_class = str_to_pdobj.get(obj_type_str, None)
            if not obj_class:
                raise ValueError(f"Invalid object type: {obj_type_str}")

            obj_kwargs = {arg: value for arg, value in obj_node.items() if arg != 'pdobj'}
            obj = obj_class(**obj_kwargs)
            list_nodes_str.append(str(obj))
        return ''.join(list_nodes_str)

    def _trnsform_edges_to_str(self) -> str:
        list_edges_str = []
        for src_obj_id, dst_obj_id, edge_data in self.graph.edges(data=True):
            src_inlet = edge_data['src_inlet']
            dst_inlet = edge_data['dst_inlet']
            list_edges_str.append(f"#X connect {src_obj_id} {src_inlet} {dst_obj_id} {dst_inlet};\n")
        return ''.join(list_edges_str)

    def add_connection(self, src_obj_id, src_inlet, dst_obj_id, dst_inlet):
        if src_obj_id not in self.graph:
            raise ValueError(f"Invalid source object id: {src_obj_id}")

        if dst_obj_id not in self.graph:
            raise ValueError(f"Invalid destination object id: {dst_obj_id}")

        self.graph.add_edge(src_obj_id, dst_obj_id, src_inlet=src_inlet, dst_inlet=dst_inlet)

    def add_object(self, obj):
        if not isinstance(obj, PdObject):
            raise TypeError(f"Object must be an instance of PdObject, not {type(obj)}")
        str_pdobj = pdobj_to_str[obj.__class__]
        self.graph.add_node(self.incremental_obj_id, pdobj=str_pdobj, **obj.__dict__)
        self.incremental_obj_id += 1

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
