# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask Web Application - Projector/beamer stage where phone users submit stickers that dance.

A real-time interactive stage display where users can submit photos from their phones, which appear as dancing animated stickers on a shared screen (perfect for events, parties, presentations).

## Commands

```bash
pip install -r requirements.txt    # Install Python dependencies (Flask, rembg, Pillow, qrcode)
python app.py                      # Run Flask server on port 5000
```

Note: First run downloads ~176MB AI model for background removal.

## Architecture

### Flask App Structure
- `app.py` - Flask server with SSE, background removal (rembg), QR code generation
- `templates/stage.html` - Stage display with animation loop (multi-sticker)
- `templates/camera.html` - Mobile photo capture, rotation controls, preview
- `static/` - Static assets (currently empty)
- `images/` - Sample images for testing

**Data Flow:**
```
Phone: capture photo → POST /process → rembg removes background → preview
Phone: rotate if needed → POST /submit → server broadcasts via SSE → stage adds sticker
Stage: SSE connection → receives add/remove events → DOM updates → animation loop
```

**Animation System** (in `templates/stage.html`):
- Single `requestAnimationFrame` loop at 60fps manages all stickers
- Random move every 80-250ms per sticker
- 8% chance of 180° mirror spin per sticker
- CSS transforms with GPU acceleration (`will-change: transform`)
- FIFO queue: max 20 stickers, oldest removed when new arrives

## Key Implementation Details

### Animation State Per Element
Each sticker tracks: `currentYRotation`, `lastMoveTime`, `nextMoveDelay`, `isSpinning`, `spinStartTime`, `spinDuration`

### Phone Photo Orientation
Server reads EXIF orientation data to auto-correct rotated phone photos (`app.py:117-132`).

### SSE Events
- `init` - Full sticker list on connect (when stage page loads)
- `add` - New sticker with position (when user submits photo)
- `remove` - Sticker ID to delete (FIFO eviction when queue exceeds 20)

### Background Removal
- Uses rembg library with AI model to remove photo backgrounds
- Processed images converted to PNG with transparency
- Base64-encoded for efficient SSE transmission

### Multi-Sticker Management
- Single page with multiple stickers (not separate windows like Electron version)
- Single animation loop manages all stickers
- No window position swapping (stickers stay in place)
- FIFO queue automatically removes oldest when limit reached
