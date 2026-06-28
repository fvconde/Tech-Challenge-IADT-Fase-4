"""
Pipeline de analise de LAUDO (documento PDF).

Fluxo:
    PDF --[StoragePort opcional]--> salvo
        --[OcrPort]----------------> texto extraido
        --[analise de texto]-------> categorias de risco + NLP (reusa o pipeline de texto)
        --[SummarizerPort]---------> resumo do laudo

Devolve as PECAS para a fusao (o router monta a resposta via fundir, tratando o laudo
como mais uma modalidade ao lado de audio/texto/video). Igual aos pipelines de audio
e video, grava um arquivo temporario porque o OCR le a partir de um caminho.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.app.ports.base import (
    DeteccaoCategoria,
    NlpPort,
    NlpResult,
    OcrPort,
    OcrResult,
    StoragePort,
    SummarizerPort,
)
from backend.app.services.text.nlp import extrair_categorias_e_nlp

logger = logging.getLogger(__name__)


@dataclass
class ResultadoLaudo:
    """Pecas produzidas pela analise do laudo (consumidas pela fusao)."""
    ocr: OcrResult
    categorias: list[DeteccaoCategoria]
    nlp: NlpResult
    resumo: str


def analisar_laudo(
    nome_arquivo: str,
    conteudo: bytes,
    ocr: OcrPort,
    nlp: NlpPort,
    summarizer: SummarizerPort,
    storage: StoragePort | None = None,
) -> ResultadoLaudo:
    """Extrai texto do PDF, analisa risco e resume."""
    # 1) (opcional) persistir o PDF recebido
    if storage is not None:
        ref = storage.salvar(f"laudo/{nome_arquivo}", conteudo)
        logger.info("Laudo armazenado em: %s", ref)

    # 2) gravar temporario para o OCR ler (precisa de um caminho)
    sufixo = Path(nome_arquivo).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
        tmp.write(conteudo)
        caminho_tmp = tmp.name

    try:
        resultado_ocr = ocr.extrair_texto(caminho_tmp)
    finally:
        try:
            Path(caminho_tmp).unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass

    texto = resultado_ocr.texto

    # 3) analise de risco (reusa o mesmo lexico/classificador do texto)
    categorias, nlp_result = extrair_categorias_e_nlp(texto, nlp)

    # 4) resumo (so se houver texto suficiente)
    resumo = summarizer.resumir(texto) if texto.strip() else ""

    return ResultadoLaudo(
        ocr=resultado_ocr, categorias=categorias, nlp=nlp_result, resumo=resumo
    )
