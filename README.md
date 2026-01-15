# Dancing Icon - Flask Web App

Projector/beamer stage where phone users submit stickers that dance.

## Quick Start

```bash
pip install -r requirements.txt
python app.py          # Run on http://localhost:5000
```

Note: First run downloads ~176MB AI model for background removal (rembg).

## How It Works

1. Open `/stage` on projector/beamer (shows QR code for easy connection)
2. Phone users scan QR code → redirects to `/camera`
3. Users capture/upload photo → background removed by AI
4. Preview and rotate if needed
5. Submit → sticker appears dancing on stage in real-time

## Features

- Real-time Server-Sent Events (SSE) for instant updates
- AI-powered background removal (rembg)
- Automatic photo orientation correction (EXIF data)
- Multi-sticker animation (single page, 60fps loop)
- FIFO queue: max 20 stickers (oldest removed automatically)
- QR code generation for easy phone connection
- Random transforms: rotation, translation, scale, skew, mirror spin

## Usage

### Stage Display (Projector)
```
http://localhost:5000/stage
```
Shows QR code overlay and dancing stickers.

### Camera Interface (Phone)
```
http://localhost:5000/camera
```
Or scan QR code from stage display.

## Architecture

- Flask server handles uploads and SSE broadcasting
- rembg removes backgrounds using AI model
- Stage page listens to SSE for new stickers
- Single animation loop manages all stickers at 60fps

See CLAUDE.md for detailed architecture and implementation details.
