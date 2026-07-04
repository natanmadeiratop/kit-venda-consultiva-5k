"""Etapa 3: regenera cada pedaço com o seu clone usando a API do Gemini.

Para cada pedaço:
  1. Envia o pedaço para o Gemini (modelo multimodal) e pede uma descrição
     detalhada da cena + transcrição literal da fala, já no formato de prompt
     para o Veo.
  2. Gera um novo vídeo com o Veo (o mesmo modelo por trás do Flow), usando a
     foto do seu clone como imagem de referência para manter a sua aparência.

Observação importante: hoje o Veo gera clipes de no máximo 8 segundos por
chamada. Se os pedaços tiverem mais de 8s, o clipe gerado sai com 8s e o vídeo
final fica mais curto que o original. Para manter a sincronia, use
``--chunk-duration 8``.
"""

import time
from pathlib import Path

VEO_MAX_SECONDS = 8

DESCRIBE_PROMPT = """\
Você é um diretor de cena escrevendo prompts para o gerador de vídeo Veo.
Assista ao vídeo em anexo e escreva UM prompt em inglês para recriar a cena
com outra pessoa (a "referência" que será fornecida como imagem) no lugar da
pessoa que aparece no vídeo. O prompt deve conter:

1. Descrição do cenário, iluminação, enquadramento e movimentos de câmera.
2. As ações e gestos da pessoa, em ordem cronológica.
3. A fala COMPLETA e LITERAL, transcrita palavra por palavra, no idioma
   original, entre aspas, para a pessoa dizer exatamente o mesmo texto.
4. O tom de voz e a energia da fala.

Refira-se à pessoa apenas como "the person from the reference image".
Responda SOMENTE com o prompt, sem comentários nem markdown.
"""


def _wait_file_active(client, uploaded, timeout: int = 300):
    """Aguarda o arquivo enviado ficar ACTIVE na Files API."""
    start = time.time()
    while uploaded.state and uploaded.state.name == "PROCESSING":
        if time.time() - start > timeout:
            raise TimeoutError(f"Arquivo {uploaded.name} não processou em {timeout}s")
        time.sleep(5)
        uploaded = client.files.get(name=uploaded.name)
    if uploaded.state and uploaded.state.name != "ACTIVE":
        raise RuntimeError(f"Arquivo {uploaded.name} em estado {uploaded.state.name}")
    return uploaded


def describe_chunk(client, chunk: Path, describe_model: str) -> str:
    """Gera o prompt do Veo a partir do conteúdo do pedaço."""
    uploaded = client.files.upload(file=str(chunk))
    uploaded = _wait_file_active(client, uploaded)
    response = client.models.generate_content(
        model=describe_model,
        contents=[uploaded, DESCRIBE_PROMPT],
    )
    text = (response.text or "").strip()
    if not text:
        raise RuntimeError(f"Gemini não retornou descrição para {chunk.name}")
    return text


def generate_clone_video(
    client,
    prompt: str,
    clone_image: Path,
    out_path: Path,
    veo_model: str,
    duration: int,
    poll_seconds: int = 15,
    timeout: int = 1800,
) -> Path:
    """Gera um clipe com o Veo usando a foto do clone como referência."""
    from google.genai import types

    with open(clone_image, "rb") as f:
        image_bytes = f.read()
    mime = "image/png" if clone_image.suffix.lower() == ".png" else "image/jpeg"
    image = types.Image(image_bytes=image_bytes, mime_type=mime)

    operation = client.models.generate_videos(
        model=veo_model,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            reference_images=[
                types.VideoGenerationReferenceImage(image=image, reference_type="asset"),
            ],
            duration_seconds=duration,
            number_of_videos=1,
        ),
    )

    start = time.time()
    while not operation.done:
        if time.time() - start > timeout:
            raise TimeoutError(f"Veo não terminou em {timeout}s (operação {operation.name})")
        time.sleep(poll_seconds)
        operation = client.operations.get(operation)

    if operation.error:
        raise RuntimeError(f"Veo falhou: {operation.error}")

    video = operation.response.generated_videos[0].video
    client.files.download(file=video)
    video.save(str(out_path))
    return out_path


def generate_all(
    workdir: Path,
    clone_image: Path,
    api_key: str,
    veo_model: str = "veo-3.1-generate-preview",
    describe_model: str = "gemini-2.5-flash",
    chunk_duration: int = 10,
) -> list[Path]:
    """Roda descrição + geração para todos os pedaços; retoma de onde parou."""
    from google import genai

    from .ffmpeg_utils import probe_duration

    client = genai.Client(api_key=api_key)

    chunks = sorted((workdir / "chunks").glob("chunk_*.mp4"))
    if not chunks:
        raise RuntimeError(f"Nenhum pedaço em {workdir / 'chunks'}. Rode a etapa 'split' antes.")

    gen_dir = workdir / "generated"
    desc_dir = workdir / "descriptions"
    gen_dir.mkdir(parents=True, exist_ok=True)
    desc_dir.mkdir(parents=True, exist_ok=True)

    if chunk_duration > VEO_MAX_SECONDS:
        print(
            f"[generate] AVISO: o Veo gera no máximo {VEO_MAX_SECONDS}s por clipe, "
            f"mas os pedaços têm {chunk_duration}s. O vídeo final ficará mais curto. "
            f"Para manter a duração, use --chunk-duration {VEO_MAX_SECONDS}."
        )

    outputs: list[Path] = []
    for chunk in chunks:
        out_path = gen_dir / chunk.name
        if out_path.exists():
            print(f"[generate] {chunk.name}: já gerado, pulando")
            outputs.append(out_path)
            continue

        desc_path = desc_dir / (chunk.stem + ".txt")
        if desc_path.exists():
            prompt = desc_path.read_text(encoding="utf-8")
            print(f"[generate] {chunk.name}: descrição já existe, reaproveitando")
        else:
            print(f"[generate] {chunk.name}: descrevendo cena com {describe_model} ...")
            prompt = describe_chunk(client, chunk, describe_model)
            desc_path.write_text(prompt, encoding="utf-8")

        duration = min(VEO_MAX_SECONDS, max(4, round(probe_duration(chunk))))
        print(f"[generate] {chunk.name}: gerando {duration}s com {veo_model} ...")
        generate_clone_video(client, prompt, clone_image, out_path, veo_model, duration)
        print(f"[generate] {chunk.name}: pronto -> {out_path}")
        outputs.append(out_path)

    return outputs
