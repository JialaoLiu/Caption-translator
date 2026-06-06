from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from collections.abc import Callable

from .asr_models import download_asr_model, is_model_downloaded
from .translator import check_ollama_model


OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/windows"


def prepare_first_run(
    asr_model_key: str,
    ollama_base_url: str,
    ollama_model: str,
    progress: Callable[[int, str], None],
) -> None:
    if not is_model_downloaded(asr_model_key):
        progress(5, "Downloading ASR model...")
        download_asr_model(asr_model_key, lambda value, message: progress(min(55, value // 2), message))
    else:
        progress(55, "ASR model already downloaded.")

    progress(60, "Checking Ollama...")
    ok, reason = check_ollama_model(ollama_base_url, ollama_model)
    if ok:
        progress(100, "Ollama and model are ready.")
        return

    if reason == "ollama_unavailable":
        ensure_ollama_installed(progress)
        start_ollama_if_possible(progress)

    progress(75, f"Pulling Ollama model: {ollama_model}...")
    pull_ollama_model(ollama_model, progress)

    ok, reason = check_ollama_model(ollama_base_url, ollama_model)
    if not ok:
        raise RuntimeError(f"Ollama setup incomplete: {reason}")
    progress(100, "First-run setup complete.")


def ensure_ollama_installed(progress: Callable[[int, str], None]) -> None:
    if shutil.which("ollama"):
        progress(65, "Ollama command found.")
        return
    if sys.platform == "win32" and shutil.which("winget"):
        progress(65, "Installing Ollama with winget...")
        run_command(
            [
                "winget",
                "install",
                "--id",
                "Ollama.Ollama",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=600,
        )
        if shutil.which("ollama"):
            progress(70, "Ollama installed.")
            return
    progress(65, "Ollama is not installed. Opening download page...")
    webbrowser.open(OLLAMA_DOWNLOAD_URL)
    raise RuntimeError("Ollama is not installed. Install Ollama, then run setup again.")


def start_ollama_if_possible(progress: Callable[[int, str], None]) -> None:
    if not shutil.which("ollama"):
        return
    progress(70, "Starting Ollama service...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:
        pass
    deadline = time.time() + 20
    while time.time() < deadline:
        if ollama_service_running():
            return
        time.sleep(1)


def pull_ollama_model(model: str, progress: Callable[[int, str], None]) -> None:
    if not shutil.which("ollama"):
        raise RuntimeError("Ollama command is not available.")
    process = subprocess.Popen(
        ["ollama", "pull", model],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if line:
            progress(85, line)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"ollama pull failed with exit code {code}")


def run_command(command: list[str], timeout: int) -> None:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"Command failed: {' '.join(command)}")


def ollama_service_running() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            response.read()
            return True
    except Exception:
        return False
