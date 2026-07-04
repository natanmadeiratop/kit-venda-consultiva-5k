"""Utilitários compartilhados de ffmpeg/ffprobe."""

import json
import shutil
import subprocess
from pathlib import Path


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"'{tool}' não encontrado no PATH. Instale o ffmpeg "
                "(ex.: sudo apt install ffmpeg / brew install ffmpeg)."
            )


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    subprocess.run(cmd, check=True)


def probe_duration(path: Path) -> float:
    """Duração do vídeo em segundos."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def probe_resolution(path: Path) -> tuple[int, int]:
    """(largura, altura) do primeiro stream de vídeo."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return int(stream["width"]), int(stream["height"])
