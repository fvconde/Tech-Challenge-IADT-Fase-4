"""Gera um AUDIO de fala sintetica (TTS) em PT-BR para testar a trilha de audio do video.

Usa edge-tts (vozes neurais da Microsoft, gratuito, sem chave). A fala e SINTETICA ->
reforca LGPD (sem voz real de paciente). O texto default cai no lexico de violencia
(`violencia_domestica`), virando categoria critica quando transcrito.

    pip install edge-tts

O edge-tts entrega MP3; o alvo default e **WAV (PCM)**, formato que o recognize_google
le no /api/audio e /api/fusion (a conversao usa o ffmpeg embutido do imageio-ffmpeg).

Uso:
    python scripts/gerar_fala_tts.py
    python scripts/gerar_fala_tts.py --texto "Nao paro de chorar, me sinto um fracasso." \
        --voz pt-BR-AntonioNeural --saida data/samples/fala.wav

Depois, acople no video com scripts/acoplar_audio.py (ou envie o WAV no campo Audio).
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

# Frase default: aciona 'violencia_domestica' (tenho medo dele / me empurrou / me ameacou).
TEXTO_PADRAO = "Tenho medo dele. Ele me empurrou e me ameaçou."


def gerar(texto: str, voz: str, rate: str, saida: str) -> None:
    try:
        import edge_tts  # import tardio: erro claro se a lib faltar
    except ImportError:
        sys.exit("edge-tts nao instalado. Rode: pip install edge-tts")

    destino = Path(saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    # edge-tts entrega MP3. Geramos num temporario e, se o alvo for WAV/FLAC,
    # convertemos para PCM (formato que o recognize_google consegue ler).
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_mp3 = tmp.name

    async def _run() -> None:
        # rate como "-5%"/"+10%" deixa a fala mais lenta/rapida (lenta ajuda a transcricao)
        communicate = edge_tts.Communicate(texto, voz, rate=rate)
        await communicate.save(tmp_mp3)

    try:
        asyncio.run(_run())
        ext = destino.suffix.lower()
        if ext == ".mp3":
            Path(tmp_mp3).replace(destino)
        else:
            _converter(tmp_mp3, destino, ext)
    finally:
        Path(tmp_mp3).unlink(missing_ok=True)
    print(f"Audio de fala gerado: {destino}")


def _converter(origem_mp3: str, destino: Path, ext: str) -> None:
    """Converte o MP3 do edge-tts para WAV/FLAC (PCM, 16k mono) via ffmpeg embutido."""
    try:
        import imageio_ffmpeg
    except ImportError:
        sys.exit(
            "Para gerar WAV/FLAC e preciso 'moviepy' (imageio-ffmpeg). "
            "Alternativa: gere .mp3 (--saida ...fala.mp3) e converta manualmente."
        )
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-i", origem_mp3, "-ar", "16000", "-ac", "1"]
    if ext == ".wav":
        cmd += ["-c:a", "pcm_s16le"]  # PCM: exigido pelo recognize_google
    cmd.append(str(destino))
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        sys.exit(f"Falha ao converter para {ext}:\n{resultado.stderr[-1500:]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera fala sintetica PT-BR (edge-tts)")
    parser.add_argument("--texto", default=TEXTO_PADRAO)
    parser.add_argument("--voz", default="pt-BR-FranciscaNeural",
                        help="ex.: pt-BR-FranciscaNeural (fem.) | pt-BR-AntonioNeural (masc.)")
    parser.add_argument("--rate", default="-5%", help='velocidade, ex.: "-5%%", "+10%%"')
    parser.add_argument("--saida", default="data/samples/fala.wav",
                        help="WAV (default) para o campo Audio; .mp3 tambem e aceito")
    args = parser.parse_args()
    gerar(args.texto, args.voz, args.rate, args.saida)
