"""Desktop overlay launcher - run with: python overlay.py

Launches a transparent, click-through fullscreen overlay using Electron.
Press Escape or Ctrl+Q to close the overlay.
"""
import subprocess
import threading
import time
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from app import app, get_local_ip


def run_flask():
    """Run Flask server in background thread"""
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False, use_reloader=False)


def wait_for_flask(timeout=15):
    """Poll Flask server until responsive or timeout

    Args:
        timeout: Maximum seconds to wait for Flask to start

    Returns:
        bool: True if Flask started successfully, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen('http://127.0.0.1:5000/', timeout=1)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def check_electron_installed():
    """Check if Electron is installed in electron/node_modules

    Returns:
        bool: True if Electron is installed, False otherwise
    """
    electron_path = Path(__file__).parent / 'electron' / 'node_modules'
    return electron_path.exists()


def launch_electron():
    """Launch Electron overlay window

    Returns:
        int: Electron process exit code
    """
    electron_dir = Path(__file__).parent / 'electron'

    try:
        # On Windows, use cmd.exe to run npx with proper PATH
        if sys.platform == 'win32':
            result = subprocess.run(
                ['cmd', '/c', 'npx', 'electron', '.'],
                cwd=str(electron_dir),
                check=False
            )
        else:
            # On Unix-like systems, use npx directly
            result = subprocess.run(
                ['npx', 'electron', '.'],
                cwd=str(electron_dir),
                check=False
            )
        return result.returncode
    except FileNotFoundError:
        print("\nERROR: Error: npx not found. Please install Node.js from https://nodejs.org/")
        print("   Download the LTS version (18.x or later)")
        return 1


if __name__ == '__main__':
    # Get local IP for camera access
    ip = get_local_ip()
    print(f"\nDancing Stickers Overlay")
    print(f"Camera: http://{ip}:5000/camera\n")

    # Check if Electron is installed
    if not check_electron_installed():
        print("ERROR: Electron not installed!")
        print("\nFirst-time setup required:")
        print("  1. Install Node.js from https://nodejs.org/ (if not already installed)")
        print("  2. Run the following commands:")
        print("     cd electron")
        print("     npm install")
        print("     cd ..")
        print("  3. Run this script again: python overlay.py")
        sys.exit(1)

    # Start Flask server in background daemon thread
    print("Starting Flask server... ", end='', flush=True)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to be responsive
    if not wait_for_flask(timeout=15):
        print("ERROR: Failed")
        print("\nERROR: Error: Flask server failed to start within 15 seconds")
        print("   Check if port 5000 is already in use")
        sys.exit(1)

    print("OK")

    # Launch Electron overlay window (blocking)
    print("Launching transparent overlay window...")
    print("Press Escape or Ctrl+Q to close the overlay.\n")

    exit_code = launch_electron()

    print("\nOK Overlay closed.")
    sys.exit(exit_code)
