"""
Windows launcher: starts the Streamlit server and opens the browser.
PyInstaller bundles this as the exe entry point.
"""
import os
import sys
import threading
import time
import webbrowser

PORT = 8501


def _open_browser():
    time.sleep(3)
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    # When frozen by PyInstaller, _MEIPASS is the unpacked temp dir
    if getattr(sys, "frozen", False):
        bundle_dir = sys._MEIPASS
    else:
        bundle_dir = os.path.dirname(os.path.abspath(__file__))

    # Point the working directory at the bundle so relative imports work
    os.chdir(bundle_dir)

    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    os.environ["STREAMLIT_SERVER_PORT"] = str(PORT)
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

    main_script = os.path.join(bundle_dir, "main.py")

    threading.Thread(target=_open_browser, daemon=True).start()

    from streamlit.web import cli as stcli
    sys.argv = [
        "streamlit", "run", main_script,
        "--server.headless=true",
        f"--server.port={PORT}",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
