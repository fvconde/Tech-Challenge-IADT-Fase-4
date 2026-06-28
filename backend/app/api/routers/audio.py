"""Endpoints de analise de AUDIO."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import NlpPort, StoragePort, TranscriptionPort
from backend.app.ports.factory import get_nlp, get_storage, get_transcription
from backend.app.services.audio.pipeline import analisar_audio

router = APIRouter(prefix="/api/audio", tags=["audio"])

# Formatos que o speech_recognition le nativamente (sem ffmpeg).
EXTENSOES_SUPORTADAS = {".wav", ".aiff", ".aif", ".flac"}


@router.post("/analyze", response_model=AnaliseRiscoResponse)
async def analisar(
    arquivo: UploadFile = File(..., description="Audio da consulta (WAV recomendado)"),
    transcription: TranscriptionPort = Depends(get_transcription),
    nlp: NlpPort = Depends(get_nlp),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Recebe um audio de consulta, transcreve e analisa sinais de risco na fala.

    ATENCAO LGPD: com TRANSCRIPTION_BACKEND=recognize_google (default), o audio e
    enviado a uma API publica do Google. Para conteudo de saude, use dados sinteticos
    ou configure um backend offline. Ver docs/decisoes-arquiteturais.md.
    """
    nome = arquivo.filename or "audio.wav"
    sufixo = "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if sufixo not in EXTENSOES_SUPORTADAS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Formato '{sufixo}' nao suportado nativamente. "
                f"Envie um dos formatos: {sorted(EXTENSOES_SUPORTADAS)}."
            ),
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo de audio vazio.")

    settings = get_settings()
    return analisar_audio(
        nome_arquivo=nome,
        conteudo=conteudo,
        transcription=transcription,
        nlp=nlp,
        storage=storage,
        idioma=settings.transcription_language,
    )
