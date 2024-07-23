import logging

import click

from pdpy.objects import Message
from pdpy.canvas import Canvas


@click.command()
@click.argument('in_filename', type=click.Path(exists=True))
@click.argument('out_filename', type=click.Path(exists=False))
def pdpy_cli(in_filename, out_filename):
    canvas = Canvas()
    canvas.read_from_file(in_filename)
    # msg_obj = Message(200, 200, 'foo, bar')
    # canvas.add_object(msg_obj)
    canvas.write_to_file(out_filename)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    pdpy_cli()
