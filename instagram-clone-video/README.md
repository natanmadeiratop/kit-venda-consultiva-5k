# Instagram → Clone Video

Ferramenta de linha de comando que:

1. **Baixa** um vídeo do Instagram a partir do link (via yt-dlp).
2. **Corta** o vídeo em pedaços sequenciais de 10 segundos (via ffmpeg).
3. **Regenera** cada pedaço com o **seu clone**, usando a API do Gemini:
   - o Gemini assiste ao pedaço e escreve um prompt com a cena, os gestos e a
     fala literal;
   - o **Veo** (o mesmo modelo por trás do Google Flow) gera o novo clipe
     usando a sua foto como imagem de referência, para o clone falar o mesmo
     texto na mesma cena.
4. **Junta** os pedaços gerados no vídeo final, na ordem original.

## Requisitos

- Python 3.10+
- ffmpeg instalado no sistema (`sudo apt install ffmpeg` ou `brew install ffmpeg`)
- Chave da API do Gemini com acesso ao Veo: <https://aistudio.google.com/apikey>
  (a geração de vídeo com Veo é paga — confira os preços no AI Studio)

```bash
cd instagram-clone-video
pip install -r requirements.txt
export GEMINI_API_KEY="sua-chave-aqui"
```

## Uso

Pipeline completo:

```bash
python -m clone_video run \
  --url "https://www.instagram.com/reel/XXXXXXXX/" \
  --clone-image minha-foto.jpg \
  --chunk-duration 8
```

O resultado fica em `output/final.mp4`. Os arquivos intermediários ficam em
`output/` (`original.mp4`, `chunks/`, `descriptions/`, `generated/`), e se
alguma etapa falhar no meio (queda de rede, limite de cota do Veo etc.), basta
rodar o mesmo comando de novo: **as etapas já concluídas são puladas** e a
geração retoma do pedaço onde parou.

### Etapas separadas

```bash
python -m clone_video download --url "https://www.instagram.com/reel/XXXX/"
python -m clone_video split --chunk-duration 8
python -m clone_video generate --clone-image minha-foto.jpg
python -m clone_video join
```

Para testar só o corte e a junção, sem gastar créditos do Veo:

```bash
python -m clone_video run --url "..." --skip-generate
```

## Avisos importantes

- **Limite de 8s do Veo**: hoje o Veo gera clipes de no máximo 8 segundos por
  chamada. O padrão do corte é 10s (como pedido), mas com pedaços de 10s cada
  clipe gerado sai com 8s e o vídeo final fica ~20% mais curto. **Recomendado:
  `--chunk-duration 8`** para manter a duração original.
- **Login do Instagram**: o Instagram costuma exigir login para servir vídeos.
  Se o download falhar, exporte os cookies do navegador (extensão
  "Get cookies.txt LOCALLY") e passe com `--cookies cookies.txt`.
- **Foto do clone**: use uma foto sua com o rosto nítido, de frente e bem
  iluminado — é ela que o Veo usa como referência de aparência.
- **Continuidade entre pedaços**: cada pedaço é gerado de forma independente,
  então pode haver pequenas variações de cenário/roupa entre um clipe e outro.
  Os prompts gerados ficam salvos em `output/descriptions/` — você pode
  editá-los à mão e rodar `generate` de novo (apague o `.mp4` correspondente
  em `output/generated/` para forçar a regeração daquele pedaço).
- **Uso responsável**: use apenas com vídeos seus ou com autorização do autor,
  e gere apenas o **seu próprio** clone (ou de alguém que autorizou). Vídeos
  gerados por IA que imitam pessoas reais sem consentimento violam os termos
  do Google e do Instagram, além da legislação de direito de imagem.

## Opções

| Opção | Padrão | Descrição |
|---|---|---|
| `--url` | — | Link do vídeo do Instagram (ou qualquer site suportado pelo yt-dlp) |
| `--clone-image` | — | Foto de referência do clone |
| `--chunk-duration` | `10` | Duração de cada pedaço em segundos (use `8` para casar com o Veo) |
| `--workdir` | `output` | Pasta de trabalho dos arquivos intermediários |
| `--veo-model` | `veo-3.1-generate-preview` | Modelo de geração de vídeo |
| `--describe-model` | `gemini-2.5-flash` | Modelo que descreve cada pedaço |
| `--cookies` | — | cookies.txt para download com login |
| `--skip-generate` | — | Só baixa, corta e junta (teste sem custo) |
