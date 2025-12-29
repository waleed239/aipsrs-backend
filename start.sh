#!/usr/bin/env bash
gunicorn app:app --bind 0.0.0.0:$PORT
# Install ffmpeg on Render (Debian/Ubuntu)
apt-get update
apt-get install -y ffmpeg

