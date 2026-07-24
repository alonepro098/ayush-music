# AYUSH MUSIC 🎧

AYUSH MUSIC is a premium, feature-complete cyberpunk-themed music streaming web application built with a Flask backend and an ultra-modern cyber-neon HTML5 frontend. 

It proxies search queries and streams high-fidelity audio streams directly from YouTube on the fly.

## Features

- **Cyberpunk Dark Theme**: Fluid dark design styled with neon pink (`#ff007f`) and neon cyan (`#00f0ff`) glows.
- **On-the-Fly Audio Streaming**: Handles byte-range seekable requests to stream audio smoothly.
- **Direct MP3 Downloads**: Dedicated downloader triggers to fetch audio directly as attachments.
- **Smart Playback Queue**: Play/Pause, Shuffle, Loop (Single/All) controls with a dynamic sidebar queue drawer.
- **My Library & Custom Playlists**: Build custom playlists and favorite tracks saved directly to the browser's persistent `LocalStorage`.
- **Sleep Timer**: Set countdown timers (5, 15, 30, 60 minutes) to pause playback automatically.
- **Dynamic Synced Lyrics**: Syncs generic lyric scripts with real-time audio playback timings.
- **Neon Ring Equalizer**: Dynamic visualizer rings drawing real-time audio wave simulations.
- **Global Keyboard Shortcuts**: Control playback via spacebar and seek/volume using keyboard arrows.

## Setup and Launch

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the web application server:
   ```bash
   python app.py
   ```

3. Open your browser and navigate to:
   - http://localhost:5000/ayush_music
