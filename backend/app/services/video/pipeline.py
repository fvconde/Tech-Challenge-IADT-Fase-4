"""
Pipeline de analise de VIDEO/IMAGEM.

Fluxo:
    arquivo --[StoragePort opcional]--> salvo
            --[VideoPort: YOLOv8]------> deteccoes (classes COCO)
            --[risk_rules]-------------> categorias de risco (DeteccaoCategoria)

Devolve o resultado bruto da deteccao (para mostrar na resposta) E as categorias de
risco (para a fusao). Igual ao pipeline de audio: grava um arquivo temporario porque
o YOLO/cv2 leem a partir de um caminho.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from backend.app.ports.base import (
    DeteccaoCategoria,
    StoragePort,
    VideoAnalysisResult,
    VideoPort,
)
from backend.app.services.video.risk_rules import avaliar_risco_visual

logger = logging.getLogger(__name__)


def analisar_video(
    nome_arquivo: str,
    conteudo: bytes,
    video: VideoPort,
    classes_foco: list[str],
    amostragem: int = 15,
    conf: float = 0.25,
    storage: StoragePort | None = None,
) -> tuple[VideoAnalysisResult, list[DeteccaoCategoria]]:
    """
    Analisa os bytes de um video/imagem e devolve (resultado_bruto, categorias_risco).
    """
    # 1) (opcional) persistir o arquivo recebido
    if storage is not None:
        ref = storage.salvar(f"video/{nome_arquivo}", conteudo)
        logger.info("Video/imagem armazenado em: %s", ref)

    # 2) gravar em arquivo temporario para o YOLO/cv2 lerem (precisam de um path)
    sufixo = Path(nome_arquivo).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
        tmp.write(conteudo)
        caminho_tmp = tmp.name

    try:
        resultado = video.analisar(
            caminho_tmp, classes_foco=classes_foco, amostragem=amostragem, conf=conf
        )
    finally:
        try:
            Path(caminho_tmp).unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass

    # 3) regras de risco: deteccoes -> categorias (mesmo tipo do texto)
    categorias = avaliar_risco_visual(resultado.deteccoes, classes_foco)
    return resultado, categorias
