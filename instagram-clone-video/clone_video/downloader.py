"""Etapa 1: baixa o vídeo do Instagram (ou de qualquer site suportado pelo yt-dlp)."""

from pathlib import Path


def download(url: str, workdir: Path, cookies_file: str | None = None) -> Path:
    """Baixa o vídeo da URL para ``workdir/original.mp4`` e retorna o caminho.

    O Instagram frequentemente exige login para servir o vídeo. Se o download
    falhar com erro de autenticação, exporte os cookies do seu navegador
    (extensão "Get cookies.txt") e passe o arquivo via ``--cookies``.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = workdir / "original.mp4"
    if out_path.exists():
        print(f"[download] já existe, pulando: {out_path}")
        return out_path

    import yt_dlp

    opts = {
        "outtmpl": str(workdir / "original.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file

    print(f"[download] baixando {url} ...")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not out_path.exists():
        # yt-dlp pode ter salvo com outra extensão se o merge não rodou
        candidates = sorted(workdir.glob("original.*"))
        if not candidates:
            raise RuntimeError("Download terminou mas nenhum arquivo foi criado.")
        out_path = candidates[0]

    print(f"[download] salvo em {out_path}")
    return out_path
