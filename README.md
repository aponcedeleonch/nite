# NiteLabs Video Mixer.

## Installation.

### Prerequisites

- [Python 3.12](https://www.python.org/downloads/)
- Recommended: [uv](https://docs.astral.sh/uv/getting-started/installation/). A convenient dependecy manager for python.

### Installation with uv (Recommended)

Open a terminal in your favorite Operating System (OS) and run:
```sh
$ make install
```

### Installing NiteLabs VideoMixer (without uv)

Open a terminal of your choice and install with:
```sh
$ pip install .
```

## Available Tools

### CLI

We have a CLI for mixing 2 videos, with an alpha layer applied to the second video. The videos can be blended using as input audio in 2 formats: a `song` or directly using the microphone from the computer, i.e. `streaming`

For both cases, the features taken from the audio are BPM and detected chromogram (pitches). You can find help running the command
```sh
nite_video_mixer --help
```
#### 1. Song

Example run:
```sh
nite_video_mixer --video-1 ../GG-ANIMATED_3.mp4 --video-2 ../GG-ANIMATED_7.mp4 --alpha ../ALPHA1.mp4 --bpm-frequency kick --blend-operation darken --blend-falloff 0.5 song --song-name ../Arden_Kres-Nite_V2.wav
```

#### 2. Stream

Example run:
```sh
nite_video_mixer --video-1 ../GG-ANIMATED_3.mp4 --video-2 ../GG-ANIMATED_7.mp4 --alpha ../ALPHA1.mp4 --bpm-frequency kick --blend-operation darken --blend-falloff 0.5 stream --playback-time-sec 5
```
