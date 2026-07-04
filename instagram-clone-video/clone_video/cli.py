"""CLI do pipeline. Uso típico:

    python -m clone_video run --url <link do Instagram> --clone-image minha-foto.jpg

Cada etapa também pode ser executada separadamente (download, split,
generate, join), sempre sobre o mesmo --workdir. Etapas já concluídas são
puladas, então dá para reexecutar o `run` depois de uma falha e ele retoma
de onde parou.
"""

import argparse
import os
import sys
from pathlib import Path

from . import downloader, joiner, splitter
from .ffmpeg_utils import require_ffmpeg

DEFAULT_WORKDIR = "output"


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--workdir",
        default=DEFAULT_WORKDIR,
        help=f"Pasta de trabalho com os arquivos intermediários (padrão: {DEFAULT_WORKDIR})",
    )


def _add_generate_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--clone-image", help="Foto do seu clone (rosto nítido, boa iluminação)")
    p.add_argument(
        "--veo-model",
        default="veo-3.1-generate-preview",
        help="Modelo Veo para gerar os clipes (padrão: veo-3.1-generate-preview)",
    )
    p.add_argument(
        "--describe-model",
        default="gemini-2.5-flash",
        help="Modelo Gemini para descrever cada pedaço (padrão: gemini-2.5-flash)",
    )


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit(
            "Erro: defina a variável de ambiente GEMINI_API_KEY com a sua chave "
            "da API do Gemini (https://aistudio.google.com/apikey)."
        )
    return key


def _clone_image(args) -> Path:
    if not args.clone_image:
        sys.exit("Erro: informe --clone-image com a foto do seu clone.")
    path = Path(args.clone_image)
    if not path.exists():
        sys.exit(f"Erro: foto do clone não encontrada: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clone_video",
        description="Baixa um vídeo do Instagram, corta em pedaços, regenera "
        "cada pedaço com o seu clone (Gemini/Veo) e junta o vídeo final.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Executa o pipeline completo")
    run.add_argument("--url", required=True, help="Link do vídeo do Instagram")
    run.add_argument("--chunk-duration", type=int, default=10, help="Duração de cada pedaço em segundos (padrão: 10; use 8 para casar com o limite do Veo)")
    run.add_argument("--cookies", help="Arquivo cookies.txt para o Instagram, se o download exigir login")
    run.add_argument("--skip-generate", action="store_true", help="Pula a geração com o clone (só baixa, corta e junta — útil para testar)")
    _add_common(run)
    _add_generate_args(run)

    dl = sub.add_parser("download", help="Etapa 1: baixa o vídeo")
    dl.add_argument("--url", required=True)
    dl.add_argument("--cookies")
    _add_common(dl)

    sp = sub.add_parser("split", help="Etapa 2: corta em pedaços")
    sp.add_argument("--chunk-duration", type=int, default=10)
    _add_common(sp)

    gen = sub.add_parser("generate", help="Etapa 3: regenera os pedaços com o clone")
    gen.add_argument("--chunk-duration", type=int, default=10)
    _add_common(gen)
    _add_generate_args(gen)

    jn = sub.add_parser("join", help="Etapa 4: junta os pedaços no vídeo final")
    jn.add_argument("--from-chunks", action="store_true", help="Junta os pedaços originais em vez dos gerados")
    _add_common(jn)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    require_ffmpeg()
    workdir = Path(args.workdir)

    if args.command == "download":
        downloader.download(args.url, workdir, args.cookies)

    elif args.command == "split":
        splitter.split(workdir / "original.mp4", workdir, args.chunk_duration)

    elif args.command == "generate":
        from . import generator

        generator.generate_all(
            workdir,
            _clone_image(args),
            _api_key(),
            veo_model=args.veo_model,
            describe_model=args.describe_model,
            chunk_duration=args.chunk_duration,
        )

    elif args.command == "join":
        parts_dir = workdir / ("chunks" if args.from_chunks else "generated")
        original = workdir / "original.mp4"
        joiner.join(parts_dir, workdir / "final.mp4", reference=original if original.exists() else None)

    elif args.command == "run":
        if not args.skip_generate:
            clone_image = _clone_image(args)
            api_key = _api_key()

        video = downloader.download(args.url, workdir, args.cookies)
        splitter.split(video, workdir, args.chunk_duration)

        if args.skip_generate:
            parts_dir = workdir / "chunks"
        else:
            from . import generator

            generator.generate_all(
                workdir,
                clone_image,
                api_key,
                veo_model=args.veo_model,
                describe_model=args.describe_model,
                chunk_duration=args.chunk_duration,
            )
            parts_dir = workdir / "generated"

        joiner.join(parts_dir, workdir / "final.mp4", reference=video)
        print("\nPipeline concluído! ✅")
        print(f"Vídeo final: {workdir / 'final.mp4'}")


if __name__ == "__main__":
    main()
