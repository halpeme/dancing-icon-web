"""Interactive launcher for Dancing Icon Stage
Run with: python launcher.py OR npm start
"""
import subprocess
import sys
import platform
import threading
import time
import urllib.request
import urllib.error

# Fix Unicode output on Windows (cp1252 can't encode box-drawing chars)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path

# Platform-specific keyboard input
if platform.system() == 'Windows':
    import msvcrt
else:
    import tty
    import termios


def colored(text, color_code):
    """Add ANSI color codes to text (cross-platform)"""
    return f"\033[{color_code}m{text}\033[0m"


def clear_screen():
    """Clear terminal screen (cross-platform)"""
    subprocess.run('cls' if platform.system() == 'Windows' else 'clear', shell=True)


def get_key():
    """Get single keypress (cross-platform)"""
    if platform.system() == 'Windows':
        # Windows: use msvcrt
        key = msvcrt.getch()
        if key in (b'\x00', b'\xe0'):  # Arrow keys prefix
            key = msvcrt.getch()
            if key == b'H':  # Up arrow
                return 'up'
            elif key == b'P':  # Down arrow
                return 'down'
        elif key == b'\r':  # Enter
            return 'enter'
        elif key == b'\x03':  # Ctrl+C
            return 'ctrl_c'
        return None
    else:
        # Unix-like: use termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # ESC sequence
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return 'up'
                    elif ch3 == 'B':
                        return 'down'
            elif ch == '\r' or ch == '\n':
                return 'enter'
            elif ch == '\x03':  # Ctrl+C
                return 'ctrl_c'
            return None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def print_banner():
    """Display launcher banner"""
    clear_screen()
    print(colored("\n┌" + "─" * 48 + "┐", "36"))
    print(colored("│  Dancing Icon Stage - Launcher                 │", "1;36"))
    print(colored("└" + "─" * 48 + "┘\n", "36"))


def print_menu(selected=0):
    """Display mode selection menu with highlighted selection"""
    print(colored("Select launch mode (↑/↓ to navigate, Enter to select):\n", "1;33"))

    # Option 1: Web mode
    prefix = colored("►", "1;32") if selected == 0 else " "
    bg = "42" if selected == 0 else ""  # Green background if selected
    if selected == 0:
        print("  " + colored(f"{prefix} [1] Web mode only", bg))
    else:
        print(f"  {prefix} " + colored("[1]", "1;32") + " Web mode only")
    print("      " + colored("→", "90") + " Flask server on localhost:5000")
    print("      " + colored("→", "90") + " Access from browser or phone\n")

    # Option 2: Desktop overlay
    prefix = colored("►", "1;35") if selected == 1 else " "
    if selected == 1:
        print("  " + colored(f"{prefix} [2] Desktop overlay only", "45"))
    else:
        print(f"  {prefix} " + colored("[2]", "1;35") + " Desktop overlay only")
    print("      " + colored("→", "90") + " Transparent fullscreen window")
    print("      " + colored("→", "90") + " Press Escape or Ctrl+Q to close\n")

    # Option 3: Both
    prefix = colored("►", "1;36") if selected == 2 else " "
    if selected == 2:
        print("  " + colored(f"{prefix} [3] Both (Web + Overlay) ★ Recommended", "46"))
    else:
        print(f"  {prefix} " + colored("[3]", "1;36") + " Both (Web + Overlay) " + colored("★ Recommended", "33"))
    print("      " + colored("→", "90") + " Flask server + transparent overlay")
    print("      " + colored("→", "90") + " Full interactive experience\n")

    print(colored("Press Ctrl+C to exit", "90"))


def launch_web_only():
    """Launch Flask web server only"""
    print(colored("\n▶ Launching Web mode...\n", "1;32"))
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print(colored("\n✓ Web server stopped", "32"))
    except subprocess.CalledProcessError as e:
        print(colored(f"\n✗ Error launching web server: {e}", "31"))
        sys.exit(1)


def launch_overlay_only():
    """Launch Electron overlay (which includes Flask)"""
    print(colored("\n▶ Launching Desktop overlay...\n", "1;35"))
    try:
        subprocess.run([sys.executable, "overlay.py"], check=True)
    except KeyboardInterrupt:
        print(colored("\n✓ Overlay closed", "32"))
    except subprocess.CalledProcessError as e:
        print(colored(f"\n✗ Error launching overlay: {e}", "31"))
        sys.exit(1)


def wait_for_flask(timeout=15):
    """Poll Flask server until responsive or timeout"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen('http://127.0.0.1:5000/', timeout=1)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


def run_flask():
    """Run Flask server in background thread"""
    from app import app
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False, use_reloader=False)


def check_electron_installed():
    """Check if Electron is installed"""
    electron_path = Path(__file__).parent / 'electron' / 'node_modules'
    return electron_path.exists()


def launch_electron():
    """Launch Electron overlay window"""
    electron_dir = Path(__file__).parent / 'electron'

    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                ['cmd', '/c', 'npx', 'electron', '.'],
                cwd=str(electron_dir),
                check=False
            )
        else:
            result = subprocess.run(
                ['npx', 'electron', '.'],
                cwd=str(electron_dir),
                check=False
            )
        return result.returncode
    except FileNotFoundError:
        print(colored("\n✗ Error: npx not found. Please install Node.js from https://nodejs.org/", "31"))
        print(colored("   Download the LTS version (18.x or later)", "90"))
        return 1


def launch_both():
    """Launch Flask + Electron overlay together"""
    print(colored("\n▶ Launching Both modes...\n", "1;36"))

    # Check if Electron is installed
    if not check_electron_installed():
        print(colored("✗ Error: Electron not installed!\n", "31"))
        print("First-time setup required:")
        print("  1. Install Node.js from https://nodejs.org/ (if not already installed)")
        print("  2. Run the following commands:")
        print("     cd electron")
        print("     npm install")
        print("     cd ..")
        print("  3. Run this launcher again: python launcher.py")
        sys.exit(1)

    # Get local IP for camera access
    from app import get_local_ip
    ip = get_local_ip()
    print(colored(f"  Camera URL: http://{ip}:5000/camera", "36"))

    # Start Flask server in background daemon thread
    print(colored("  Starting Flask server... ", "90"), end='', flush=True)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Wait for Flask to be responsive
    if not wait_for_flask(timeout=15):
        print(colored("✗ Failed", "31"))
        print(colored("\n✗ Error: Flask server failed to start within 15 seconds", "31"))
        print(colored("   Check if port 5000 is already in use", "90"))
        sys.exit(1)

    print(colored("✓ OK", "32"))

    # Launch Electron overlay window (blocking)
    print(colored("  Launching transparent overlay window...", "90"))
    print(colored("  Press Escape or Ctrl+Q to close the overlay.\n", "90"))

    exit_code = launch_electron()

    print(colored("\n✓ Overlay closed", "32"))
    sys.exit(exit_code)


def select_option():
    """Interactive menu selection with arrow keys"""
    selected = 2  # Default to option 3 (Both - Recommended)

    while True:
        print_banner()
        print_menu(selected)

        try:
            key = get_key()

            if key == 'up':
                selected = (selected - 1) % 3
            elif key == 'down':
                selected = (selected + 1) % 3
            elif key == 'enter':
                return selected + 1  # Return 1, 2, or 3
            elif key == 'ctrl_c':
                raise KeyboardInterrupt

        except KeyboardInterrupt:
            print(colored("\n\n✓ Launcher cancelled", "32"))
            sys.exit(0)


def main():
    """Main launcher entry point"""
    try:
        choice = select_option()

        if choice == 1:
            launch_web_only()
        elif choice == 2:
            launch_overlay_only()
        elif choice == 3:
            launch_both()

    except KeyboardInterrupt:
        print(colored("\n\n✓ Launcher cancelled", "32"))
        sys.exit(0)
    except Exception as e:
        print(colored(f"\n✗ Unexpected error: {e}", "31"))
        sys.exit(1)


if __name__ == '__main__':
    main()
