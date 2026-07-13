"""
Pipeline de analise de AUDIO (fatia vertical ponta-a-ponta).

Fluxo:
    audio (WAV) --[StoragePort]--> salvo em disco
                --[TranscriptionPort]--> texto
                --[servico de texto]--> analise de risco
                --> AnaliseRiscoResponse (com a transcricao preenchida)

Tudo via portas: trocar local<->cloud nao muda este arquivo.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import NlpPort, StoragePort, TranscriptionPort
from backend.app.services.text.nlp import analisar_texto

logger = logging.getLogger(__name__)


def analisar_audio(
    nome_arquivo: str,
    conteudo: bytes,
    transcription: TranscriptionPort,
    nlp: NlpPort,
    storage: StoragePort | None = None,
    idioma: str = "pt-BR",
) -> AnaliseRiscoResponse:
    """
    Recebe os bytes de um WAV, transcreve e analisa o risco.

    'storage' e opcional: se fornecido, guarda o audio (audita/reuso). A transcricao
    precisa de um caminho de arquivo, entao usamos um arquivo temporario quando
    o storage e local/ausente.
    """
    # 1) (opcional) persistir o audio recebido
    if storage is not None:
        ref = storage.salvar(f"audio/{nome_arquivo}", conteudo)
        logger.info("Audio armazenado em: %s", ref)

    # 2) gravar em arquivo temporario para a transcricao ler (AudioFile exige path)
    sufixo = Path(nome_arquivo).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
        tmp.write(conteudo)
        caminho_tmp = tmp.name

    try:
        transcricao = transcription.transcrever(caminho_tmp, idioma=idioma)
    finally:
        # limpa o temporario
        try:
            Path(caminho_tmp).unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass

    # 3) analisar o texto transcrito (reusa todo o pipeline de texto)
    if not transcricao.texto.strip():
        # audio vazio / nao compreendido: devolve resposta neutra explicita
        resposta = analisar_texto("", nlp, fonte="audio")
    else:
        resposta = analisar_texto(transcricao.texto, nlp, fonte="audio")

    # 4) anexar metadados de transcricao
    resposta.transcricao = transcricao.texto
    resposta.backend_transcricao = transcricao.backend
    return resposta
