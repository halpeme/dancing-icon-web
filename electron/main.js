const { app, BrowserWindow, screen } = require('electron');
const http = require('http');

const FLASK_URL = 'http://127.0.0.1:5000/?mode=overlay';
const FLASK_HOST = '127.0.0.1';
const FLASK_PORT = 5000;

/**
 * Poll Flask server until it's responsive
 * @param {number} maxAttempts - Maximum number of polling attempts
 * @param {number} delayMs - Delay between attempts in milliseconds
 * @returns {Promise<void>}
 */
function waitForFlask(maxAttempts = 30, delayMs = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const checkFlask = () => {
      attempts++;

      const req = http.get(`http://${FLASK_HOST}:${FLASK_PORT}/`, (res) => {
        if (res.statusCode === 200) {
          console.log('✓ Flask server is ready');
          resolve();
        } else {
          retryOrFail();
        }
      });

      req.on('error', (err) => {
        if (attempts >= maxAttempts) {
          reject(new Error(`Flask server not responsive after ${maxAttempts} attempts: ${err.message}`));
        } else {
          setTimeout(checkFlask, delayMs);
        }
      });

      req.end();
    };

    const retryOrFail = () => {
      if (attempts >= maxAttempts) {
        reject(new Error(`Flask server returned non-200 status after ${maxAttempts} attempts`));
      } else {
        setTimeout(checkFlask, delayMs);
      }
    };

    checkFlask();
  });
}

/**
 * Calculate combined bounds for all displays
 * @returns {Object} { x, y, width, height, displayCount, displays }
 */
function getCombinedDisplayBounds() {
  const displays = screen.getAllDisplays();

  if (displays.length === 0) {
    throw new Error('No displays detected');
  }

  // Calculate bounding box that encompasses all displays
  let minX = Infinity, minY = Infinity;
  let maxX = -Infinity, maxY = -Infinity;

  displays.forEach(display => {
    const { x, y, width, height } = display.bounds;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + width);
    maxY = Math.max(maxY, y + height);
  });

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
    displayCount: displays.length,
    displays: displays
  };
}

/**
 * Create transparent, fullscreen, click-through overlay window (stays on top)
 */
function createWindow() {
  const bounds = getCombinedDisplayBounds();

  console.log(`Detected ${bounds.displayCount} display(s):`);
  bounds.displays.forEach((d, i) => {
    console.log(`  Display ${i}: ${d.bounds.width}x${d.bounds.height} at (${d.bounds.x}, ${d.bounds.y})`);
  });
  console.log(`Combined canvas: ${bounds.width}x${bounds.height} at (${bounds.x}, ${bounds.y})`);

  const win = new BrowserWindow({
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    hasShadow: false,
    skipTaskbar: false,
    show: false,  // Don't show until bounds are set
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false  // Keep animations at 60fps
    }
  });

  // IMPORTANT: Set bounds AFTER creation to span multiple displays
  // Windows doesn't allow creating windows larger than primary display in constructor
  win.setBounds({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height
  });

  // Verify window bounds after setBounds
  const actualBounds = win.getBounds();
  console.log(`Window bounds after setBounds: ${actualBounds.width}x${actualBounds.height} at (${actualBounds.x}, ${actualBounds.y})`);

  // Enable click-through (pass all mouse events to windows below)
  win.setIgnoreMouseEvents(true, { forward: true });

  // Use higher priority level to stay above all windows even with click-through
  // 'screen-saver' level keeps window above normal windows, toolbars, etc.
  win.setAlwaysOnTop(true, 'screen-saver');

  // Keyboard shortcuts
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return;

    // Escape key or Ctrl+Q to close
    if (input.key === 'Escape' || (input.control && input.key === 'q')) {
      app.quit();
    }
  });

  // Load Flask overlay page
  win.loadURL(FLASK_URL);

  // Log dimensions as seen by the web page after load
  win.webContents.on('did-finish-load', () => {
    win.webContents.executeJavaScript('({width: window.innerWidth, height: window.innerHeight, screenWidth: window.screen.width, screenHeight: window.screen.height})')
      .then(dims => {
        console.log(`Frontend sees window as: ${dims.width}x${dims.height}`);
        console.log(`Frontend sees screen as: ${dims.screenWidth}x${dims.screenHeight}`);
      });

    // Show window after page loads and bounds are set
    win.show();
  });

  // Optional: Open DevTools for debugging (comment out for production)
  // win.webContents.openDevTools({ mode: 'detach' });

  return win;
}

// Electron app lifecycle
app.whenReady().then(async () => {
  try {
    console.log('Waiting for Flask server to start...');
    await waitForFlask();
    console.log('Launching transparent overlay window...');
    createWindow();
  } catch (err) {
    console.error('Error:', err.message);
    console.error('Make sure Flask server is running on port 5000');
    app.quit();
  }
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  app.quit();
});

// macOS: Re-create window when dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
