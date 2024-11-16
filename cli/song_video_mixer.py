import asyncio
from functools import wraps
from pathlib import Path
from typing import List, Optional

import click

from nite.logging import configure_module_logging
from nite.video_mixer.audio.audio_action import AudioActions, AudioActionBPM, AudioActionPitch, BPMActionFrequency
from nite.video_mixer.audio.audio_processing import ChromaIndex, AudioSampleFeatures
from nite.video_mixer.audio.audio_io import AudioAnalyzer
from nite.video_mixer.audio.audio_processing import AudioProcessor
from nite.video_mixer.blender import BlenderMath, BlendWithSong, BlendModes
from nite.video_mixer.streamer import VideoCombinerSong
from nite.video_mixer.video.video import VideoFramesPath
from nite.video_mixer.video.video_io import NiteVideo, VideoStream

logger = configure_module_logging('nite.cli.song_video_mixer')

PITCH_CHOICES = {member.name: member.value for member in ChromaIndex}
BPM_FREQUENCY_CHOICES = {member.name: member.value for member in BPMActionFrequency}
BLEND_MODES_CHOICES = {member.name: member.value for member in BlendModes}


async def process_audio(song_name: Path) -> AudioSampleFeatures:
    audio_processor = AudioProcessor()
    audio_analyzer = AudioAnalyzer(audio_processor)
    audio_features = await audio_analyzer.analyze_song(song_name)
    return audio_features


async def initialize_audio_actions(
                                    song_name: Path,
                                    bpm_frequency: Optional[int],
                                    min_pitch: Optional[int],
                                    max_pitch: Optional[int]
                                ) -> AudioActions:
    if bpm_frequency is None and min_pitch is None and max_pitch is None:
        raise ValueError('At least bpm_frequency or min_pitch and max_pitch must be set.')

    if (min_pitch is not None and max_pitch is None) or (min_pitch is None and max_pitch is not None):
        raise ValueError('Both min_pitch and max_pitch must be set.')

    action_list = []
    if bpm_frequency is not None:
        bpm_action = AudioActionBPM(BPMActionFrequency(bpm_frequency))
        action_list.append(bpm_action)

    if min_pitch is not None and max_pitch is not None:
        pitch_action = AudioActionPitch(min_pitch=ChromaIndex(min_pitch), max_pitch=ChromaIndex(max_pitch))
        action_list.append(pitch_action)

    actions = AudioActions(action_list)
    audio_features = await process_audio(song_name)
    actions.set_features(audio_features)
    return actions


def intialize_stream_params(width: int, height: int) -> VideoStream:
    return VideoStream(width=width, height=height)


async def initialize_videos(video_1: Path, video_2: Path, alpha: Path, video_stream: VideoStream) -> List[VideoFramesPath]:
    nite_video_1 = NiteVideo(video_1, video_stream)
    nite_video_2 = NiteVideo(video_2, video_stream)
    alpha_video = NiteVideo(alpha, video_stream, is_alpha=True)

    async with asyncio.TaskGroup() as tg:
        task_video_1 = tg.create_task(nite_video_1())
        task_video_2 = tg.create_task(nite_video_2())
        task_alpha = tg.create_task(alpha_video())

    return [task_video_1.result(), task_video_2.result(), task_alpha.result()]


def initialize_blender(blend_operation) -> BlendWithSong:
    blender_math = BlenderMath(BlendModes(blend_operation))
    blender = BlendWithSong(blender_math)
    return blender


async def initialize_video_combiner(
                                    song_name: Path,
                                    video_1: Path,
                                    video_2: Path,
                                    alpha: Path,
                                    width: int,
                                    height: int,
                                    bpm_frequency: Optional[int],
                                    min_pitch: Optional[int],
                                    max_pitch: Optional[int],
                                    blend_operation: str
                                ) -> VideoCombinerSong:
    video_stream = intialize_stream_params(width, height)
    videos = await initialize_videos(video_1, video_2, alpha, video_stream)
    blender = initialize_blender(blend_operation)
    actions = await initialize_audio_actions(song_name, bpm_frequency, min_pitch, max_pitch)
    return VideoCombinerSong(videos, blender, actions)


# Got this hack to use click with async from: https://github.com/pallets/click/issues/85
def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@click.command()
@click.option(
    '--song-name', required=True,
    type=click.Path(exists=True, dir_okay=False), help='The song to process.'
)
@click.option(
    '--video-1', required=True,
    type=click.Path(exists=True, dir_okay=False), help='The video 1 to mix.'
)
@click.option(
    '--video-2', required=True,
    type=click.Path(exists=True, dir_okay=False), help='The video 2 to mix.'
)
@click.option(
    '--alpha', required=True,
    type=click.Path(exists=True, dir_okay=False), help='The alpha to use over video 2.'
)
@click.option(
    '--width', required=False,
    type=int, default=640, help='The width of the video.'
)
@click.option(
    '--height', required=False,
    type=int, default=480, help='The height of the video.'
)
@click.option(
    '--bpm-frequency', required=False,
    type=click.Choice(list(BPM_FREQUENCY_CHOICES.keys())), help='The BPM frequency.'
)
@click.option(
    '--min-pitch', required=False,
    type=click.Choice(list(PITCH_CHOICES.keys())), help='The minimum pitch to act.'
)
@click.option(
    '--max-pitch', required=False,
    type=click.Choice(list(PITCH_CHOICES.keys())), help='The maximum pitch to act.'
)
@click.option(
    '--blend-operation', required=False,
    type=click.Choice(BLEND_MODES_CHOICES.keys()), help='The math operation to apply.'
)
@coro
async def song_video_mixer(
    song_name, video_1, video_2, alpha, width, height, bpm_frequency, min_pitch, max_pitch, blend_operation
):
    video_combiner = await initialize_video_combiner(
        Path(song_name),
        Path(video_1),
        Path(video_2),
        Path(alpha),
        width,
        height,
        BPM_FREQUENCY_CHOICES.get(bpm_frequency, None),
        PITCH_CHOICES.get(min_pitch, None),
        PITCH_CHOICES.get(max_pitch, None),
        blend_operation
    )
    await video_combiner.stream()


if __name__ == '__main__':
    song_video_mixer()
