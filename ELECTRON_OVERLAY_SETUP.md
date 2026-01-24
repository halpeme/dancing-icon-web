# Electron Transparent Overlay - Setup Guide

## What Changed

Migrated from PyWebView (which doesn't support transparency on Windows) to Electron (which does).

### Files Created
- `electron/main.js` - Electron main process with transparent window configuration
- `electron/package.json` - Node.js dependencies (just Electron)

### Files Updated
- `overlay.py` - Replaced PyWebView code with Electron subprocess launcher
- `.gitignore` - Added `node_modules/` entries
- `requirements.txt` - Removed `pywebview>=5.0.0` dependency

### Files Unchanged (Already Compatible)
- `app.py` - Overlay mode detection already implemented (lines 95-98)
- `templates/stage.html` - Transparent CSS already conditional (lines 17-21)
- All animation, SSE, and Flask logic works as-is

## First-Time Setup

### 1. Install Node.js (if not already installed)
Download and install Node.js 18+ LTS from https://nodejs.org/

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Electron
```bash
cd electron
npm install
cd ..
```

## Running the Overlay

```bash
python overlay.py
```

**Controls:**
- Press **Escape** or **Ctrl+Q** to close the overlay
- Alt+F4 also works

## Features

✅ **Transparent window** - Desktop shows through empty areas
✅ **Click-through** - Can interact with desktop/windows below overlay
✅ **Fullscreen overlay** - Covers entire screen
✅ **60fps animations** - Hardware accelerated, no throttling
✅ **Real-time SSE** - Stickers appear instantly when submitted from phone
✅ **Simple launch** - Just run `python overlay.py`

## Testing the Overlay

### 1. Verify Flask Overlay Mode
```bash
python app.py
# Visit http://localhost:5000/?mode=overlay in browser
# Should see transparent background, no QR code visible
```

### 2. Run Transparent Overlay
```bash
python overlay.py
# Desktop should show through empty areas
# Stickers should be opaque and animated
```

### 3. Test Click-Through
- Try clicking desktop icons through the overlay
- Try dragging windows behind the overlay
- All mouse events should pass through to desktop

### 4. Test Sticker Submission
- Open phone camera: `http://<local-ip>:5000/camera`
- Take/upload photo from phone
- Verify sticker appears on overlay with animation

### 5. Test Close
- Press **Escape** → overlay should close
- Press **Ctrl+Q** → overlay should close
- Press **Alt+F4** → overlay should close

## Architecture

```
Python (overlay.py)
  ├── Thread 1: Flask server (daemon, port 5000)
  └── Thread 2: Main - launches Electron subprocess (blocking)
                └── Electron process
                    └── Renderer: loads http://127.0.0.1:5000/?mode=overlay
```

## Troubleshooting

### "npx not found" Error
**Solution:** Install Node.js from https://nodejs.org/ (LTS version)

### "Electron not installed" Error
**Solution:** Run the following commands:
```bash
cd electron
npm install
cd ..
```

### "Flask server failed to start" Error
**Solution:** Check if port 5000 is already in use. Stop any other Flask apps or processes using port 5000.

### Transparency Not Working
**Requirements:** Windows 10 or later with Desktop Window Manager (DWM) enabled.
Transparency uses GPU compositing and requires modern Windows.

### Animations Choppy
- Electron setting `backgroundThrottling: false` prevents tab throttling
- Should run at 60fps with hardware acceleration
- Check Task Manager → GPU usage to verify hardware acceleration

## System Requirements

- **OS:** Windows 10 or later (for DWM transparent window support)
- **Node.js:** 18+ LTS
- **Python:** 3.8+
- **Disk Space:** ~200MB for Electron + ~176MB for rembg AI model

## Development Notes

### Enable DevTools
Edit `electron/main.js` and uncomment line 76:
```javascript
win.webContents.openDevTools({ mode: 'detach' });
```

### Adjust Polling Timeout
Edit `electron/main.js` line 89 to change Flask polling attempts:
```javascript
await waitForFlask(30, 500);  // 30 attempts, 500ms delay = 15s total
```

### Change Keyboard Shortcuts
Edit `electron/main.js` lines 67-71 to modify close shortcuts.
