# CLAUDE.md

## Project Overview

- Real-time interactive stage: users submit photos from phones → dancing animated stickers
- Dual-mode: web UI (localhost:5000) or transparent desktop overlay (Electron)
- Flask backend + Electron frontend with SSE for real-time updates

## Commands

```bash
# Python setup (first time)
pip install -r requirements.txt    # Flask, rembg, Pillow, qrcode

# Node.js setup (first time)
cd electron && npm install

# RECOMMENDED: Interactive launcher (choose mode at startup)
python launcher.py
# OR from electron directory:
npm start

# Direct launch modes:
python app.py          # Web mode only - localhost:5000
python overlay.py      # Desktop overlay only - fullscreen transparent
```

Note: First run downloads ~176MB rembg AI model. Overlay requires Electron.

## File Structure

```
launcher.py                 Interactive mode selector (web/overlay/both)
app.py                      Flask server (SSE, background removal, QR)
overlay.py                  Electron launcher (Flask + Electron)
electron/main.js            Transparent multi-display window
templates/stage.html        Animation loop + effects engine
templates/camera.html       Mobile capture + rotation
templates/controls.html     Operator UI (effects, race, gallery controls)
static/sounds/              5 entrance MP3s
```

## Architecture

### Stack
- **Backend**: Flask - SSE broadcast, rembg, QR generation
- **Frontend**: stage.html - 60fps requestAnimationFrame loop
- **Desktop**: Electron + Python launcher
- **Phone**: camera.html - capture, file upload, rotation

### Data Flow
```
Phone: capture/upload → POST /process → preview
Phone: POST /submit → Flask SSE broadcast
Stage: SSE → add/remove events → DOM → animation
Desktop: overlay.py → Flask → Electron → stage.html?mode=overlay
```

### Animation Engine
- 60fps loop manages all stickers
- Entrance: 'pop' (bounce) or 'superhero' (drop+bounce)
- Movement: random every 80-250ms with easing
- Mirror spin: 8% chance, 180° Y-rotation, 300-600ms
- Sound: random entrance-{1-5}.mp3
- FIFO: max 20 stickers, auto-remove oldest

### Electron Overlay
- Transparent fullscreen, click-through, always-on-top
- Multi-display: spans all screens (combined bounds minX/minY → maxX/maxY)
- Escape/Ctrl+Q to close

## Key Implementation Details

### SSE Events
- `init` - Full sticker list on connect
- `add` - New sticker: id, image_base64, x, y, sound
- `remove` - Sticker ID (FIFO eviction > 20)

### Effects System
- Toggled via `POST /effect` with `{name, active}` — SSE-broadcast to all clients
- Active effects: `rainbow`, `strobe`, `disco_spin`, `size_pulse`, `gravity_bounce`, `motion_trail`
- `motion_trail`: each sticker has 5 pre-created ghost `<div>` elements (`trailGhosts`) + `trailHistory[]` (last 5 positions); ghosts fade opacity 0.45→0.05
- Deactivation cleanup blocks in SSE handler (per-effect) + `removeSticker()` removes ghost DOM nodes

### Sticker State
Tracks: `currentYRotation`, `lastMoveTime`, `nextMoveDelay`, `isSpinning`, `spinStartTime`, `spinDuration`, `entranceProgress`, `entranceStyle`, `trailGhosts`, `trailHistory`

### EXIF Auto-Correction
Server reads EXIF orientation, auto-corrects rotated phone photos pre-removal.

### Multi-Display
- Electron sets bounds AFTER window creation (Windows transparency limitation)
- Canvas coordinate system spans all displays
- Stickers move freely across screen boundaries

### Launch Flow
- `overlay.py`: Flask background thread → wait localhost:5000 (15s timeout, 0.5s poll) → launch Electron
- Electron checks node_modules, loads stage.html with overlay param
