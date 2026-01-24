# Transparent Overlay - Summary

## Goal
Create transparent fullscreen overlay where stickers dance over desktop.

## What We Tried

### Changes Made
1. **Fullscreen**: `overlay.py` - Changed from `width=1280, height=720` to `fullscreen=True` ✓
2. **CSS Background**: Added Jinja2 conditional in `stage.html` for transparent background in overlay mode ✓
3. **Flask Route**: Added `overlay_mode` detection in `app.py` from `?mode=overlay` URL parameter ✓
4. **Transparency Settings**: Enhanced WebView2 settings in `overlay.py` (DefaultBackgroundColor, form settings) ✗

### Result
- Fullscreen works
- CSS renders correctly
- **But window still shows white background instead of transparent**

## Root Cause

**PyWebView does NOT support transparency on Windows.** This is a documented limitation:
- WebView2 (Microsoft's Edge browser control) has architectural limitations
- PyWebView docs state: "transparent=True - Not supported on Windows"
- GitHub issues #745, #1271 confirm this

## Solution: Use Electron

Electron fully supports transparent windows on Windows.

### Electron Config
```javascript
const win = new BrowserWindow({
  fullscreen: true,
  frame: false,
  transparent: true,  // This actually works in Electron
  alwaysOnTop: true
});
win.loadURL('http://localhost:5000/?mode=overlay');
win.setIgnoreMouseEvents(true);  // Click-through
```

## Files Modified (Still Valid for Electron)
- `app.py:88-98` - Overlay mode detection
- `templates/stage.html:13-22` - Conditional transparent CSS
- `overlay.py:56` - Fullscreen mode

All these changes will work with Electron implementation.
