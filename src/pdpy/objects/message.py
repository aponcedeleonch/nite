import logging

from pdpy.objects.object import PdObject


logger = logging.getLogger(__name__)


class Message(PdObject):

    def __init__(self, x: int, y: int, msg: str):
        super().__init__(x, y)
        self.msg = self._clean_msg(msg)

    def _clean_msg(self, msg: str):
        
        def __check_and_clean_char(msg: str, char: str):
            if char in msg:
                logger.info(f'Removing invalid character `{char}` from message: {msg}')
                msg = msg.replace(char, '')
            return msg
        
        for char in [';', '\n', ',']:
            msg = __check_and_clean_char(msg, char)
        
        return msg
    
    @property
    def str_id(self):
        return '#X msg'
    
    def __str__(self):
        return f"{self.str_id} {self.x} {self.y} {self.msg};\n"
