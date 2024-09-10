import os

# Video metadata variables
METADATA_FILENAME = os.getenv('METADATA_FILENAME', 'metadata.json')
SUFFIX_NITE_VIDEO_FOLDER = os.getenv('SUFFIX_NITE_VIDEO_FOLDER', 'nite_video')

# Audio variables
# AUDIO_SAMPLING_RATE in Hz. 44100 is a common value, samples per second.
AUDIO_SAMPLING_RATE = int(float(os.getenv('AUDIO_SAMPLING_RATE', 44100)))
# AUDIO_CHANNELS is the number of channels. 1 for mono, 2 for stereo.
AUDIO_CHANNELS = int(float(os.getenv('AUDIO_CHANNELS', 1)))

# Variables mainly for the video mixer
TERMINATE_MESSAGE = os.getenv('TERMINATE_MESSAGE', 'Terminate')
MAX_ACION_WORKERS = int(float(os.getenv('MAX_ACION_WORKERS', 5)))
KEEPALIVE_TIMEOUT = int(float(os.getenv('KEEPALIVE_TIMEOUT', 5)))

LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO')
