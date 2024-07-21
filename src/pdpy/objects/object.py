from abc import ABC, abstractmethod


class PdObject(ABC):

    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    @property
    @abstractmethod
    def str_id(self):
        pass

    @abstractmethod
    def __str__(self):
        pass
