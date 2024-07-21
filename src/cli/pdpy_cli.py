import logging

import click

from pdpy.objects.message import Message
from pdpy.canvas.canvas import Canvas


@click.command()
@click.argument('filename', type=click.Path(exists=False))
def pdpy_cli(filename):
    msg_obj = Message(100, 100, 'Hello, world!')
    canvas = Canvas()
    canvas.add_object(msg_obj)
    canvas.write_to_file(filename)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    pdpy_cli()
