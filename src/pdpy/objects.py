from abc import ABC, abstractmethod
import logging
from typing import Optional, List

from pdpy.utils import clean_pd_str, transform_str_to_int


logger = logging.getLogger(__name__)



class PdObject(ABC):

    def __init__(self, x: Optional[int] = None, y: Optional[int] = None):
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
        line = clean_pd_str(line)
        obj_str_part = line.split(' ')
        self.x = transform_str_to_int(obj_str_part[2])
        self.y = transform_str_to_int(obj_str_part[3])
        return obj_str_part[4:]

    @abstractmethod
    def read_line(self, line: str) -> None:
        pass


class Message(PdObject):

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
        obj_list = super()._common_process_line(line)
        self._set_msg(' '.join(obj_list))


class ObjBox(PdObject):

    def __init__(self, x: Optional[int] = None, y: Optional[int] = None, obj_args: Optional[List] = None):
        super().__init__(x, y)
        self.obj_args = obj_args or []

    @property
    def str_id(self) -> str:
        return '#X obj'

    def __str__(self) -> str:
        return f"{self.str_id} {self.x} {self.y} {' '.join(self.obj_args)};\n"
    
    def read_line(self, line: str) -> None:
        obj_list = super()._common_process_line(line)
        self.obj_args = obj_list


pdobj_to_str = {
    Message: 'msg',
    ObjBox: 'obj'
}

str_to_pdobj = {str_rep: pdobj for pdobj, str_rep in pdobj_to_str.items()}
