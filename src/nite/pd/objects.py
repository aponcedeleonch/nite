from abc import ABC, abstractmethod
import logging
from typing import Optional, List

from pdpy.utils import clean_pd_str, transform_str_to_int


logger = logging.getLogger(__name__)



class PdObject(ABC):

    def __init__(self):
        pass

    @property
    @abstractmethod
    def str_id(self) -> str:
        pass

    @abstractmethod
    def __str__(self) -> str:
        pass

    def _common_process_line(self, line: str) -> List:
        line = clean_pd_str(line)
        obj_str_elems = line.split(' ')
        return obj_str_elems[2:]

    @abstractmethod
    def read_line(self, line: str) -> None:
        pass


class PdPositionObject(PdObject):

    def __init__(self, x: Optional[int] = None, y: Optional[int] = None):
        super().__init__()
        self.x = x or 10
        self.y = y or 10

    @property
    @abstractmethod
    def str_id(self) -> str:
        pass

    @abstractmethod
    def __str__(self) -> str:
        pass

    def _common_process_line(self, line: str) -> List:
        obj_str_elems = super()._common_process_line(line)
        self.x = transform_str_to_int(obj_str_elems[0])
        self.y = transform_str_to_int(obj_str_elems[1])
        return obj_str_elems[2:]

    @abstractmethod
    def read_line(self, line: str) -> None:
        pass


class Message(PdPositionObject):

    def __init__(self, x: Optional[int] = None, y: Optional[int] = None, msg: Optional[str] = None):
        super().__init__(x, y)
        self._set_msg(msg)
    
    @property
    def str_id(self) -> str:
        return '#X msg'

    def __str__(self) -> str:
        return f"{self.str_id} {self.x} {self.y} {self.msg};\n"
    
    def _set_msg(self, msg: Optional[str]):
        self.msg = clean_pd_str(msg)
    
    def read_line(self, line: str) -> None:
        obj_str_elems = super()._common_process_line(line)
        self._set_msg(' '.join(obj_str_elems))


class ObjBox(PdPositionObject):

    def __init__(self, x: Optional[int] = None, y: Optional[int] = None, obj_args: Optional[List] = None):
        super().__init__(x, y)
        self.obj_args = obj_args or []

    @property
    def str_id(self) -> str:
        return '#X obj'

    def __str__(self) -> str:
        str_obj_args = ' '.join([str(arg) for arg in self.obj_args])
        return f"{self.str_id} {self.x} {self.y} {str_obj_args};\n"
    
    def read_line(self, line: str) -> None:
        self.obj_args = super()._common_process_line(line)


class DeclareLib(PdObject):

    def __init__(self, lib_name: Optional[str] = None):
        super().__init__()
        self.lib_name = lib_name
    
    @property
    def str_id(self) -> str:
        return '#X declare'

    def __str__(self) -> str:
        return f"{self.str_id} -lib {self.lib_name};\n"

    def read_line(self, line: str) -> None:
        obj_str_elems = super()._common_process_line(line)
        self.lib_name = obj_str_elems[1]


pdobj_to_str = {
    Message: 'msg',
    ObjBox: 'obj',
    DeclareLib: 'declare'
}

str_to_pdobj = {str_rep: pdobj for pdobj, str_rep in pdobj_to_str.items()}
