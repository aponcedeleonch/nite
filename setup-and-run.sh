#!/usr/bin/env bash
set -e

LOGFILE="$HOME/nite-startup.log"
echo "=== $(date) Starting Nite setup & run ===" >> "$LOGFILE"

# 1) Install deps & uv
sudo apt-get update >> "$LOGFILE" 2>&1
sudo apt-get upgrade -y >> "$LOGFILE" 2>&1
sudo apt-get install -y libportaudio2 libportaudiocpp0 portaudio19-dev curl wmctrl >> "$LOGFILE" 2>&1

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv…" >> "$LOGFILE" 2>&1
  curl -LsSf https://astral.sh/uv/install.sh | sh >> "$LOGFILE" 2>&1
fi

# ensure uv is on PATH
export PATH="$HOME/.local/bin:$PATH"

# 2) Go to project dir
cd "$HOME/nite"

# 3) Sync & any other uv setup
make install >> "$LOGFILE" 2>&1

# 4) Launch the mixer & force it fullscreen
nite_video_mixer \
  --video-1 ../GG-ANIMATED_3.mp4 \
  --video-2 ../GG-ANIMATED_7.mp4 \
  --alpha   ../ALPHA1.mp4 \
  --bpm-frequency kick \
  --blend-operation darken \
  --blend-falloff 0.5 \
  song \
  --song-name ../Arden_Kres-Nite_V2.wav >> "$LOGFILE" 2>&1 &

# give it a moment to open
sleep 2

# fullscreen the active window
wmctrl -r :ACTIVE: -b add,fullscreen

# wait on the mixer so systemd knows if it dies
wait

# Make sure to make the script executable:
# chmod +x setup-and-run.sh