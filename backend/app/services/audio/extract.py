"""
Extracao da trilha de AUDIO de um video (ponte video -> audio -> transcricao).

Usa MoviePy (import lazy; requer ffmpeg, ja necessario para o pydub). E um helper
LOCAL: MoviePy nao e um servico externo/rede, entao nao precisa de Port/adapter
(mesma logica com que usamos cv2 dentro dos adapters de video).

Fluxo de uso: o pipeline de video escreve o upload num arquivo temporario, chama
esta funcao para gerar um WAV da trilha, transcreve esse WAV com o TranscriptionPort
existente e reaproveita todo o pipeline de texto/NLP. Nenhuma logica nova de NLP.
"""

from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def extrair_audio_de_video(caminho_video: str, fps: int = 16000) -> str:
    """
    Extrai a trilha de audio de um video para um WAV temporario e devolve o caminho.

    - fps=16000: taxa adequada para reconhecimento de fala (mantem o arquivo leve).
    - O CHAMADOR e responsavel por apagar o WAV retornado (tempfile).
    - Levanta RuntimeError se o MoviePy nao estiver instalado ou se o video nao
      tiver trilha de audio.
    """
    # Import lazy, tolerante as duas APIs (MoviePy 2.x e 1.x).
    try:
        from moviepy import VideoFileClip  # MoviePy >= 2.0
    except ImportError:
        try:
            from moviepy.editor import VideoFileClip  # MoviePy 1.x
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError(
                "Extracao de audio de video requer 'moviepy' (e ffmpeg no SO). "
                "Instale com 'pip install moviepy' ou desligue VIDEO_TRANSCREVER_AUDIO."
            ) from exc

    # cria o caminho do WAV temporario (fecha o descritor; o MoviePy reabre por path)
    fd, caminho_wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        with VideoFileClip(caminho_video) as clip:
            if clip.audio is None:
                raise RuntimeError("O video nao possui trilha de audio para transcrever.")
            # logger=None silencia a barra de progresso do MoviePy nos logs da API.
            clip.audio.write_audiofile(caminho_wav, fps=fps, logger=None)
    except Exception:
        # se algo falhar, nao deixa lixo temporario para tras
        try:
            os.unlink(caminho_wav)
        except OSError:  # pragma: no cover
            pass
        raise

    logger.info("Trilha de audio extraida do video para: %s", caminho_wav)
    return caminho_wav
