"""
Entrypoint da API FastAPI.

Rodar:
    uvicorn backend.app.main:app --reload

Docs interativas: http://127.0.0.1:8000/docs
O app sobe 100% local (sem nenhuma credencial de nuvem) por padrao.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routers import audio, fusion, laudo, text, video
from backend.app.core.config import get_settings
from backend.app.core.logging import configurar_logging

configurar_logging()
settings = get_settings()

app = FastAPI(
    title="IA Multimodal — Saúde da Mulher (Tech Challenge Fase 4)",
    description=(
        "Apoio à decisão clínica a partir de texto, áudio, vídeo e laudos. "
        "**NÃO** emite diagnóstico: gera alertas para a equipe especializada. "
        "Roda local por padrão; nuvem (AWS) é opcional via adapters."
    ),
    version="0.1.0",
)

# CORS: libera o frontend Angular em desenvolvimento (ng serve usa a porta 4200).
# Sem isso, o navegador bloqueia as chamadas do Angular para a API (origens diferentes).
# Em producao, restrinja allow_origins ao dominio real do frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(text.router)
app.include_router(audio.router)
app.include_router(video.router)
app.include_router(laudo.router)
app.include_router(fusion.router)


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
            "video": settings.video_backend,
            "ocr": settings.ocr_backend,
            "summarizer": settings.summarizer_backend,
        },
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Healthcheck simples."""
    return {"status": "ok"}
