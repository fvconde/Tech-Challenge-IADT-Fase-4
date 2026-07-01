"""Endpoints de analise de TEXTO."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.models.schemas import AnaliseRiscoResponse, TextoRequest
from backend.app.ports.base import NlpPort
from backend.app.ports.factory import get_nlp
from backend.app.services.text.nlp import analisar_texto

router = APIRouter(prefix="/api/text", tags=["texto"])


@router.post(
    "/analyze", response_model=AnaliseRiscoResponse, summary="Analisar relato textual"
)
def analisar(
    payload: TextoRequest,
    nlp: NlpPort = Depends(get_nlp),
) -> AnaliseRiscoResponse:
    """
    Analisa um texto (relato/transcricao) e devolve categorias de risco,
    sentimento, nivel de alerta e acao recomendada para a equipe.

    Roda 100% offline (sem nuvem) por padrao. Util para testar a pipeline sem audio.
    """
    return analisar_texto(payload.texto, nlp)
