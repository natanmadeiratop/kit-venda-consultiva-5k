"""Etapa 4: junta os pedaços (gerados ou originais) no vídeo final."""

import tempfile
from pathlib import Path

from .ffmpeg_utils import probe_duration, probe_resolution, run_ffmpeg


def join(
    parts_dir: Path,
    out_path: Path,
    reference: Path | None = None,
    fps: int = 30,
) -> Path:
    """Concatena todos os chunk_*.mp4 de ``parts_dir`` em ``out_path``.

    Os clipes gerados pelo Veo podem sair com resolução/fps diferentes do
    original, então cada pedaço é normalizado para o mesmo formato antes da
    concatenação (o concat do ffmpeg exige streams idênticos). A resolução
    alvo vem de ``reference`` (normalmente o vídeo original, para preservar
    o formato vertical dos Reels) ou, na falta dele, do primeiro pedaço.
    """
    parts = sorted(parts_dir.glob("chunk_*.mp4"))
    if not parts:
        raise RuntimeError(f"Nenhum pedaço encontrado em {parts_dir}")

    width, height = probe_resolution(reference if reference else parts[0])
    # dimensões ímpares quebram o yuv420p
    width -= width % 2
    height -= height % 2

    print(f"[join] normalizando e juntando {len(parts)} pedaços de {parts_dir} ...")
    with tempfile.TemporaryDirectory(prefix="clone-video-join-") as tmp:
        tmp_dir = Path(tmp)
        normalized: list[Path] = []
        for part in parts:
            norm = tmp_dir / part.name
            run_ffmpeg([
                "-i", str(part),
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                norm.as_posix(),
            ])
            normalized.append(norm)

        list_file = tmp_dir / "list.txt"
        list_file.write_text(
            "".join(f"file '{p.as_posix()}'\n" for p in normalized), encoding="utf-8"
        )
        run_ffmpeg([
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_path),
        ])

    print(f"[join] vídeo final: {out_path} ({probe_duration(out_path):.1f}s)")
    return out_path
