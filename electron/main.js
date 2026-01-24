const { app, BrowserWindow } = require('electron');
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
 * Create transparent, fullscreen, click-through overlay window (stays on top)
 */
function createWindow() {
  const win = new BrowserWindow({
    fullscreen: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    hasShadow: false,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      backgroundThrottling: false  // Keep animations at 60fps
    }
  });

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
