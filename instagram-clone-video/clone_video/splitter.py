"""Etapa 2: corta o vídeo original em pedaços de N segundos, em sequência."""

from pathlib import Path

from .ffmpeg_utils import probe_duration, run_ffmpeg


def split(video: Path, workdir: Path, chunk_duration: int = 10) -> list[Path]:
    """Corta ``video`` em pedaços sequenciais de ``chunk_duration`` segundos.

    Cada pedaço é extraído com um corte reencodado (-ss/-t), o que garante a
    duração exata independentemente da posição dos keyframes (com "-c copy" o
    corte só acontece nos keyframes existentes e as durações saem erradas).
    O último pedaço pode ser mais curto que N segundos.

    Retorna a lista de pedaços em ordem: chunk_000.mp4, chunk_001.mp4, ...
    """
    chunks_dir = workdir / "chunks"
    existing = sorted(chunks_dir.glob("chunk_*.mp4"))
    if existing:
        print(f"[split] {len(existing)} pedaços já existem em {chunks_dir}, pulando")
        return existing

    chunks_dir.mkdir(parents=True, exist_ok=True)
    total = probe_duration(video)
    print(f"[split] cortando {video.name} ({total:.1f}s) em pedaços de {chunk_duration}s ...")

    index = 0
    start = 0.0
    while start < total - 0.05:  # ignora sobra menor que 50ms no fim
        run_ffmpeg([
            "-ss", f"{start:.3f}",
            "-t", str(chunk_duration),
            "-i", str(video),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            str(chunks_dir / f"chunk_{index:03d}.mp4"),
        ])
        index += 1
        start += chunk_duration

    chunks = sorted(chunks_dir.glob("chunk_*.mp4"))
    for c in chunks:
        print(f"[split]   {c.name}: {probe_duration(c):.1f}s")
    print(f"[split] {len(chunks)} pedaços gerados em {chunks_dir}")
    return chunks
