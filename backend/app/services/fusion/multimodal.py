"""
Fusao multimodal: monta UM alerta unico a partir de varias modalidades.

Recebe as pecas BRUTAS de cada modalidade (categorias de risco do texto/audio e/ou
do video, alem do sentimento e das deteccoes visuais), combina as categorias com a
regra documentada em fusion/alerts.py (combinar_categorias) e produz a resposta da
API ja com o nivel de alerta e a acao recomendada.

Aceita 1 ou mais modalidades:
- so texto/audio  -> alerta unimodal de texto;
- so video        -> alerta unimodal de video;
- texto + video   -> alerta multimodal (com boost de corroboracao quando cabivel).
"""

from __future__ import annotations

from backend.app.models.schemas import (
    AnaliseRiscoResponse,
    CategoriaRiscoSchema,
    DeteccaoVisualSchema,
    EntidadeSchema,
    SentimentoSchema,
)
from backend.app.ports.base import (
    DeteccaoCategoria,
    NlpResult,
    SentimentResult,
    VideoAnalysisResult,
)
from backend.app.services.fusion.alerts import avaliar_alerta, combinar_categorias

# Sentimento neutro padrao (usado quando nao ha modalidade de texto/audio).
_SENTIMENTO_NEUTRO = SentimentResult(rotulo="neutro", score=0.0, backend="n/a")


def fundir(
    *,
    categorias_texto: list[DeteccaoCategoria] | None = None,
    nlp_result: NlpResult | None = None,
    categorias_video: list[DeteccaoCategoria] | None = None,
    video_result: VideoAnalysisResult | None = None,
    transcricao: str | None = None,
    backend_transcricao: str | None = None,
) -> AnaliseRiscoResponse:
    """Combina as modalidades fornecidas em um unico AnaliseRiscoResponse."""
    modalidades: list[str] = []
    listas: list[list[DeteccaoCategoria]] = []

    # Modalidade de texto/audio presente quando passamos categorias_texto (mesmo vazia).
    if categorias_texto is not None:
        modalidades.append("texto")
        listas.append(categorias_texto)

    # Modalidade de video presente quando passamos categorias_video (mesmo vazia).
    if categorias_video is not None:
        modalidades.append("video")
        listas.append(categorias_video)

    # combina as categorias de todas as modalidades (boost de corroboracao incluso)
    combinadas = combinar_categorias(*listas) if listas else []

    # sentimento vem do texto; neutro se so houver video
    sentimento = nlp_result.sentimento if nlp_result else _SENTIMENTO_NEUTRO

    nivel, acao = avaliar_alerta(combinadas, sentimento)

    resposta = AnaliseRiscoResponse(
        categorias_risco=[
            CategoriaRiscoSchema(
                categoria=c.categoria, score=c.score, evidencias=c.evidencias
            )
            for c in combinadas
        ],
        sentimento=SentimentoSchema(
            rotulo=sentimento.rotulo, score=sentimento.score, backend=sentimento.backend
        ),
        entidades=[
            EntidadeSchema(texto=e.texto, tipo=e.tipo)
            for e in (nlp_result.entidades if nlp_result else [])
        ],
        nivel_alerta=nivel,
        acao_recomendada=acao,
        modalidades=modalidades,
        transcricao=transcricao,
        backend_transcricao=backend_transcricao,
        backend_nlp=(nlp_result.sentimento.backend if nlp_result else None),
    )

    # anexa detalhes de video, se houver
    if video_result is not None:
        resposta.deteccoes_video = [
            DeteccaoVisualSchema(classe=d.classe, confianca=d.confianca, frame=d.frame)
            for d in video_result.deteccoes
        ]
        resposta.frames_analisados = video_result.frames_analisados
        resposta.backend_video = video_result.backend

    return resposta
