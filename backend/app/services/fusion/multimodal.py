"""
Fusao multimodal: monta UM alerta unico a partir de varias modalidades.

Recebe as pecas BRUTAS de cada modalidade (categorias de risco do texto/audio e/ou
do video, alem do sentimento e das deteccoes visuais), combina as categorias com a
regra documentada em fusion/alerts.py (combinar_categorias) e produz a resposta da
API ja com o nivel de alerta e a acao recomendada.

Aceita 1 ou mais modalidades:
- so texto/audio   -> alerta unimodal de texto;
- so video         -> alerta unimodal de video;
- so laudo (PDF)   -> alerta unimodal de documento;
- varias juntas    -> alerta multimodal (com boost de corroboracao quando cabivel).
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
    Entidade,
    NlpResult,
    SentimentResult,
    VideoAnalysisResult,
)
from backend.app.services.fusion.alerts import avaliar_alerta, combinar_categorias

# Sentimento neutro padrao (usado quando nao ha modalidade de texto).
_SENTIMENTO_NEUTRO = SentimentResult(rotulo="neutro", score=0.0, backend="n/a")


def _combinar_sentimento(*nlp_results: NlpResult | None) -> SentimentResult:
    """
    Quando ha mais de uma fonte de texto (ex.: transcricao + laudo), escolhemos o
    sentimento MAIS NEGATIVO (menor score). Em apoio a decisao clinica, o sinal de
    risco mais forte deve prevalecer. Sem nenhuma fonte -> neutro.
    """
    presentes = [r.sentimento for r in nlp_results if r is not None]
    if not presentes:
        return _SENTIMENTO_NEUTRO
    return min(presentes, key=lambda s: s.score)


def _juntar_entidades(*nlp_results: NlpResult | None) -> list[Entidade]:
    """Une as entidades de todas as fontes de texto (sem deduplicar, simples)."""
    entidades: list[Entidade] = []
    for r in nlp_results:
        if r is not None:
            entidades.extend(r.entidades)
    return entidades


def fundir(
    *,
    categorias_texto: list[DeteccaoCategoria] | None = None,
    nlp_result: NlpResult | None = None,
    categorias_video: list[DeteccaoCategoria] | None = None,
    video_result: VideoAnalysisResult | None = None,
    categorias_laudo: list[DeteccaoCategoria] | None = None,
    nlp_laudo: NlpResult | None = None,
    transcricao: str | None = None,
    backend_transcricao: str | None = None,
    texto_documento: str | None = None,
    resumo: str | None = None,
    backend_ocr: str | None = None,
    backend_summarizer: str | None = None,
) -> AnaliseRiscoResponse:
    """Combina as modalidades fornecidas em um unico AnaliseRiscoResponse."""
    modalidades: list[str] = []
    listas: list[list[DeteccaoCategoria]] = []

    # Cada modalidade esta "presente" quando passamos a sua lista (mesmo vazia).
    if categorias_texto is not None:
        modalidades.append("texto")
        listas.append(categorias_texto)
    if categorias_video is not None:
        modalidades.append("video")
        listas.append(categorias_video)
    if categorias_laudo is not None:
        modalidades.append("laudo")
        listas.append(categorias_laudo)

    # combina as categorias de todas as modalidades (boost de corroboracao incluso)
    combinadas = combinar_categorias(*listas) if listas else []

    # sentimento/entidades vem das fontes de TEXTO (transcricao/texto + laudo)
    sentimento = _combinar_sentimento(nlp_result, nlp_laudo)
    entidades = _juntar_entidades(nlp_result, nlp_laudo)

    nivel, acao = avaliar_alerta(combinadas, sentimento)

    # backend de NLP (para rastreabilidade): o da fonte usada, se houver
    backend_nlp = None
    if nlp_result is not None:
        backend_nlp = nlp_result.sentimento.backend
    elif nlp_laudo is not None:
        backend_nlp = nlp_laudo.sentimento.backend

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
        entidades=[EntidadeSchema(texto=e.texto, tipo=e.tipo) for e in entidades],
        nivel_alerta=nivel,
        acao_recomendada=acao,
        modalidades=modalidades,
        transcricao=transcricao,
        backend_transcricao=backend_transcricao,
        backend_nlp=backend_nlp,
        texto_documento=texto_documento,
        resumo=resumo,
        backend_ocr=backend_ocr,
        backend_summarizer=backend_summarizer,
    )

    # anexa detalhes de video, se houver
    if video_result is not None:
        resposta.deteccoes_video = [
            DeteccaoVisualSchema(classe=d.classe, confianca=d.confianca, frame=d.frame)
            for d in video_result.deteccoes
        ]
        resposta.frames_analisados = video_result.frames_analisados
        resposta.backend_video = video_result.backend
        resposta.imagem_anotada_b64 = video_result.imagem_anotada_b64

    return resposta
