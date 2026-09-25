"""Whisper worker stub. See README."""
from pathlib import Path
import subprocess, sys

def to_wav(src, dst):
    subprocess.check_call(["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)])

if __name__ == "__main__":
    print("Plug whisper here. usage: python worker_transcribe.py track.mp3")
