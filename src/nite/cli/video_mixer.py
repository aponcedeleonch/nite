import asyncio
from pathlib import Path

import click

from nite.audio.audio_action import BPMActionFrequency
from nite.audio.audio_processing import ChromaIndex
from nite.nite_logging import configure_nite_logging
from nite.video_mixer.blender import BlendModes
from nite.video_mixer.factories import VideoCombinerFactory

PITCH_CHOICES = {member.name: member.value for member in ChromaIndex}
BPM_FREQUENCY_CHOICES = {member.name: member.value for member in BPMActionFrequency}
BLEND_MODES_CHOICES = {member.name: member.value for member in BlendModes}


@click.group()
@click.option(
    "--video-1",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="The path to the first video file to mix. This video acts as the base layer.",
)
@click.option(
    "--video-2",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help=(
        "The path to the second video file to mix. "
        "This video acts as the blend layer, which will be blended over the base layer."
    ),
)
@click.option(
    "--alpha",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help=(
        "The path to the alpha channel file, which determines the transparency "
        "of the blend layer over the base layer."
    ),
)
@click.option(
    "--width",
    required=False,
    type=int,
    default=640,
    help="The width of the output video. Default is 640.",
)
@click.option(
    "--height",
    required=False,
    type=int,
    default=480,
    help="The height of the output video. Default is 480.",
)
@click.option(
    "--bpm-frequency",
    required=False,
    type=click.Choice(list(BPM_FREQUENCY_CHOICES.keys())),
    help=(
        "The BPM frequency to act on. "
        "This allows the video blending to be synchronized with the beat of the song."
    ),
)
@click.option(
    "--min-pitch",
    required=False,
    type=click.Choice(list(PITCH_CHOICES.keys())),
    help="The minimum pitch to act on. Parameter used in conjunction with --max-pitch.",
)
@click.option(
    "--max-pitch",
    required=False,
    type=click.Choice(list(PITCH_CHOICES.keys())),
    help="The maximum pitch to act on. Parameter used in conjunction with --min-pitch.",
)
@click.option(
    "--blend-operation",
    required=True,
    type=click.Choice(list(BLEND_MODES_CHOICES.keys())),
    help="The blend operation to apply between the base and blend layers.",
)
@click.option(
    "--blend-falloff",
    required=False,
    default=0.0,
    type=float,
    help=(
        "The blend falloff time in seconds. This determines how quickly the blend "
        "effect transitions between the base and blend layers. Default is 0.0."
    ),
)
@click.pass_context
def cli(
    ctx,
    video_1,
    video_2,
    alpha,
    width,
    height,
    bpm_frequency,
    min_pitch,
    max_pitch,
    blend_operation,
    blend_falloff,
):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj["video_1"] = Path(video_1)
    ctx.obj["video_2"] = Path(video_2)
    ctx.obj["alpha"] = Path(alpha)
    ctx.obj["width"] = width
    ctx.obj["height"] = height
    ctx.obj["bpm_frequency"] = BPM_FREQUENCY_CHOICES.get(bpm_frequency, None)
    ctx.obj["min_pitch"] = PITCH_CHOICES.get(min_pitch, None)
    ctx.obj["max_pitch"] = PITCH_CHOICES.get(max_pitch, None)
    ctx.obj["blend_operation"] = blend_operation
    ctx.obj["blend_falloff"] = blend_falloff
    configure_nite_logging()


@cli.command()
@click.option(
    "--song-name",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help=(
        "The path to the audio file (song) to process. The command will analyze this "
        "song to extract audio features like BPM and pitch for synchronization with the videos."
    ),
)
@click.pass_context
def song(ctx, song_name):
    """
    The song command is designed to mix two video files with an alpha channel
    using audio-driven effects. It allows you to synchronize video mixing with audio features
    such as BPM (Beats Per Minute) and pitch.

    \b
    Example:
    nite_video_mixer \\
        --video-1 ./video1.mp4 \\
        --video-2 ./video2.mp4 \\
        --alpha ./alpha.png \\
        --width 1280 \\
        --height 720 \\
        --bpm-frequency kick \\
        --blend-operation add \\
        --blend-falloff 2.0 \\
        song \\
        --song-name ./music.mp3

    This example will mix video1.mp4 and video2.mp4 using the alpha channel alpha.mp4,
    with the output video dimensions set to 1280x720. The mixing will be synchronized with
    the BPM of music.mp3, and the blend operation will use the OVERLAY mode with a
    falloff time of 2.0 seconds. The pitch range for synchronization will be between 48 and 72.
    """
    video_combiner_factory = VideoCombinerFactory(
        video_1=ctx.obj["video_1"],
        video_2=ctx.obj["video_2"],
        alpha=ctx.obj["alpha"],
        width=ctx.obj["width"],
        height=ctx.obj["height"],
        bpm_frequency=ctx.obj["bpm_frequency"],
        min_pitch=ctx.obj["min_pitch"],
        max_pitch=ctx.obj["max_pitch"],
        blend_operation=ctx.obj["blend_operation"],
        blend_falloff=ctx.obj["blend_falloff"],
        song_name=Path(song_name),
    )
    video_combiner = asyncio.run(video_combiner_factory.get_song_config())
    video_combiner.stream()


@cli.command()
@click.option(
    "--playback-time-sec",
    required=True,
    type=int,
    help="The time to wait before killing the stream.",
)
@click.pass_context
def stream(ctx, playback_time_sec):
    """
    The stream command is designed to mix two video files with an alpha channel
    """
    video_combiner_factory = VideoCombinerFactory(
        video_1=ctx.obj["video_1"],
        video_2=ctx.obj["video_2"],
        alpha=ctx.obj["alpha"],
        width=ctx.obj["width"],
        height=ctx.obj["height"],
        bpm_frequency=ctx.obj["bpm_frequency"],
        min_pitch=ctx.obj["min_pitch"],
        max_pitch=ctx.obj["max_pitch"],
        blend_operation=ctx.obj["blend_operation"],
        blend_falloff=ctx.obj["blend_falloff"],
        playback_time_sec=playback_time_sec,
    )
    video_combiner = asyncio.run(video_combiner_factory.get_stream_config())
    video_combiner.stream()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
