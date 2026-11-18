import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_server(process, url):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Packaged server exited with code {process.returncode}")
        try:
            with urlopen(url + "/info", timeout=2) as response:
                if json.load(response)["status"] == "OK":
                    return
        except (TimeoutError, URLError):
            time.sleep(0.5)
    raise RuntimeError("Timed out waiting for the packaged server")


def check_startup(bundle):
    executable = bundle / ("MMVCServerSIO.exe" if os.name == "nt" else "MMVCServerSIO")
    log = bundle / "vcclient.log"
    keep_log = log.exists()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    with tempfile.TemporaryDirectory(prefix="voice-changer-smoke-") as root:
        env = dict(os.environ, HOST="127.0.0.1", PORT=str(port), MODEL_DIR=str(Path(root) / "models"))
        url = f"http://127.0.0.1:{port}"
        try:
            with subprocess.Popen(
                [str(executable), "--launch-browser", "false", "--skip-downloads"],
                env=env,
                stdin=subprocess.DEVNULL,
            ) as process:
                try:
                    wait_for_server(process, url)
                    with urlopen(url + "/", timeout=5) as page:
                        assert page.headers.get_content_type() == "text/html"
                    with urlopen(url + "/index.js", timeout=5) as script:
                        assert script.read(1), "The packaged frontend script is empty"
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
        finally:
            if not keep_log:
                log.unlink(missing_ok=True)


if __name__ == "__main__":
    check_startup(Path(sys.argv[1]).resolve())
