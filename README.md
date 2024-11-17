# NiteLabs Video Mixer.

## Installation.

### Prerequisites

- [Python 3.12](https://www.python.org/downloads/)

### Installation with virtual environment (Optional recommendation)

After installing python 3.12 open a terminal in your favorite Operating System (OS) and run:
```sh
$ make install
```

This should install a python virtual environment wiht all the dependencies needed. The name of the virtualenv created wiht the previous make command should be `venv`.

If everything went good, activate the virtual environment.
```sh
$ source venv/bin/activate
```

### Installing NiteLabs VideoMixer (without virtual environment)

Open a terminal of your choice and install with:
```sh
$ pip install .
```

## Available Tools

### CLI

We have a CLI for mixing 2 videos, with an alpha layer applied to the second video using the features of a song. The features taken from the song are BPM and detected chromogram (pitches). You can find help running the command
```sh
$ python cli/song_video_mixer.py --help
```

Example run:
```sh
$ python cli/song_video_mixer.py --song-name ../Arden_Kres-Nite_V2.wav --video-1 ../GG-ANIMATED_3.mp4 --video-2 ../GG-ANIMATED_7.mp4 --alpha ../ALPHA1.mp4 --bpm-frequency kick --blend-operation darken --blend-falloff 0.5;
```
