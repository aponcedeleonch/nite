import os
from pathlib import Path

# Video metadata variables
METADATA_FILENAME = os.getenv("METADATA_FILENAME", "metadata.json")
SUFFIX_NITE_VIDEO_FOLDER = os.getenv("SUFFIX_NITE_VIDEO_FOLDER", "nite_video")
VIDEO_LOCATION = os.getenv("VIDEO_LOCATION", str(Path(__file__).parent.absolute() / "video"))

# Audio variables
# AUDIO_SAMPLING_RATE in Hz. 44100 is a common value, samples per second.
AUDIO_SAMPLING_RATE = int(float(os.getenv("AUDIO_SAMPLING_RATE", 44100)))
# AUDIO_CHANNELS is the number of channels. 1 for mono, 2 for stereo.
AUDIO_CHANNELS = int(float(os.getenv("AUDIO_CHANNELS", 1)))

# Audio processing variables
# These values were found to be the most suitable for the test tracks.
# See experiments notebook for more details.
# Number of seconds to keep in the buffer for BPM detection
BPM_BUFFER_SECONDS_MIN = int(float(os.getenv("BPM_BUFFER_SECONDS_MIN", 15)))
BPM_BUFFER_SECONDS_MAX = int(float(os.getenv("BPM_BUFFER_SECONDS_MAX", 15)))
# Number of BPMs to keep in the buffer for BPM detection
BPM_BUFFER_BPMS_MIN = int(float(os.getenv("BPM_BUFFER_BPMS_MIN", 3)))
BPM_BUFFER_BPMS_MAX = int(float(os.getenv("BPM_BUFFER_BPMS_MAX", 3)))
# Number of seconds to remove after each detection
BPM_BUFFER_SECS_REMOVE = int(float(os.getenv("BPM_BUFFER_SECS_REMOVE", 0)))

# Variables mainly for the video mixer
KEEPALIVE_TIMEOUT = int(float(os.getenv("KEEPALIVE_TIMEOUT", 5)))

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

# Variables for converting audio to stream
STREAM_CHUNK = int(float(os.getenv("STREAM_CHUNK", 1024)))
