from pdpy.objects.object import PdObject


class Canvas:

    def __init__(self, x=None, y=None, width=None, height=None, font_size=None):
        self.x = x or -100
        self.y = y or -100
        self.width = width or 400
        self.height = height or 400
        self.font_size = font_size or 12
        self.objects = []

    def add_object(self, obj):
        if not isinstance(obj, PdObject):
            raise TypeError(f"Object must be an instance of PdObject, not {type(obj)}")
        self.objects.append(obj)

    def __str__(self):
        obj_lines = ''.join(str(obj) for obj in self.objects)
        return f"#N canvas {self.x} {self.y} {self.width} {self.height} {self.font_size};\n" + obj_lines
    
    def write_to_file(self, filename):
        with open(filename, 'w') as f:
            f.write(str(self))
