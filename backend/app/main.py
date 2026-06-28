"""
Entrypoint da API FastAPI.

Rodar:
    uvicorn backend.app.main:app --reload

Docs interativas: http://127.0.0.1:8000/docs
O app sobe 100% local (sem nenhuma credencial de nuvem) por padrao.
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.routers import audio, text, video
from backend.app.core.config import get_settings
from backend.app.core.logging import configurar_logging

configurar_logging()
settings = get_settings()

app = FastAPI(
    title="IA Multimodal - Saude da Mulher (Tech Challenge Fase 4)",
    description=(
        "Apoio a decisao clinica a partir de texto/audio/video. "
        "NAO emite diagnostico: gera alertas para a equipe especializada. "
        "Roda local por padrao; nuvem (AWS) e opcional via adapters."
    ),
    version="0.1.0",
)

app.include_router(text.router)
app.include_router(audio.router)
app.include_router(video.router)


@app.get("/", tags=["meta"])
def raiz() -> dict:
    """Informacoes basicas e estado dos backends selecionados."""
    return {
        "app": "IA Multimodal - Saude da Mulher",
        "versao": "0.1.0",
        "aviso_etico": "Apoio a decisao. NAO e diagnostico.",
        "backends": {
            "storage": settings.storage_backend,
            "nlp": settings.nlp_backend,
            "transcription": settings.transcription_backend,
        },
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck simples."""
    return {"status": "ok"}
