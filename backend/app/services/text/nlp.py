"""
Servico de analise de risco em TEXTO.

Orquestra as pecas (cada uma testavel isoladamente):
  1. NlpPort        -> sentimento + entidades (local por padrao, Comprehend opcional)
  2. risk_lexicon   -> categorias de risco por regras (explicaveis)
  3. classifier     -> categoria prevista por sklearn (generaliza p/ frases novas)
  4. fusion.alerts  -> nivel de alerta + acao recomendada

Devolve um AnaliseRiscoResponse pronto para a API. O endpoint de AUDIO reutiliza
este mesmo servico, apenas preenchendo o campo 'transcricao' antes.
"""

from __future__ import annotations

from backend.app.models.schemas import (
    AchadoSchema,
    AnaliseRiscoResponse,
    CategoriaRiscoSchema,
    EntidadeSchema,
    SentimentoSchema,
)
from backend.app.ports.base import NlpPort, NlpResult
from backend.app.services.fusion.alerts import avaliar_alerta
from backend.app.services.text.achados import detectar_achados
from backend.app.services.text.classifier import prever_categoria
from backend.app.services.text.risk_lexicon import (
    DeteccaoCategoria,
    detectar_categorias,
)

# Probabilidade minima para o classificador "votar" numa categoria.
LIMIAR_CLASSIFICADOR = 0.55


def extrair_categorias_e_nlp(
    texto: str, nlp: NlpPort
) -> tuple[list[DeteccaoCategoria], NlpResult]:
    """
    Devolve as PECAS BRUTAS da analise de texto (sem montar o alerta final):
      - lista de categorias de risco (lexico + classificador);
      - resultado de NLP (sentimento + entidades).

    A fusao multimodal reusa esta funcao para pegar as categorias do texto e
    combina-las com as do video antes de decidir o alerta.
    """
    # 1) sentimento + entidades (via porta - local ou cloud)
    nlp_result = nlp.analisar(texto)

    # 2) categorias por lexico (regras transparentes)
    categorias = detectar_categorias(texto)

    # 3) classificador estatistico complementa o lexico
    cat_prevista, prob = prever_categoria(texto)
    if cat_prevista and prob >= LIMIAR_CLASSIFICADOR:
        categorias = _mesclar_classificador(categorias, cat_prevista, prob)

    return categorias, nlp_result


def analisar_texto(
    texto: str, nlp: NlpPort, fonte: str = "texto"
) -> AnaliseRiscoResponse:
    """Executa a analise completa de risco sobre um texto.

    'fonte' rotula a origem dos achados por trecho (ex.: "audio" quando este
    servico e reusado pelo pipeline de audio sobre a transcricao).
    """
    categorias, nlp_result = extrair_categorias_e_nlp(texto, nlp)

    # fusao -> nivel de alerta + acao
    nivel, acao = avaliar_alerta(categorias, nlp_result.sentimento)

    # categorizacao por trecho (chunk), complementar ao agregado acima
    achados = detectar_achados(texto, fonte)

    return AnaliseRiscoResponse(
        categorias_risco=[
            CategoriaRiscoSchema(
                categoria=c.categoria, score=c.score, evidencias=c.evidencias
            )
            for c in categorias
        ],
        sentimento=SentimentoSchema(
            rotulo=nlp_result.sentimento.rotulo,
            score=nlp_result.sentimento.score,
            backend=nlp_result.sentimento.backend,
        ),
        entidades=[
            EntidadeSchema(texto=e.texto, tipo=e.tipo) for e in nlp_result.entidades
        ],
        nivel_alerta=nivel,
        acao_recomendada=acao,
        backend_nlp=nlp_result.sentimento.backend,
        achados=[
            AchadoSchema(
                fonte=a.fonte,
                trecho=a.trecho,
                categoria=a.categoria,
                score=a.score,
                metadados=a.metadados,
            )
            for a in achados
        ],
    )


def _mesclar_classificador(
    categorias: list[DeteccaoCategoria], cat_prevista: str, prob: float
) -> list[DeteccaoCategoria]:
    """Funde a predicao do classificador com as deteccoes do lexico."""
    evidencia_clf = f"classificador (prob={prob:.2f})"
    for c in categorias:
        if c.categoria == cat_prevista:
            # ja detectada pelo lexico: reforca o score e registra a concordancia
            c.score = round(max(c.score, prob), 3)
            c.evidencias.append(evidencia_clf)
            return categorias
    # categoria nova, vista so pelo classificador
    categorias.append(
        DeteccaoCategoria(
            categoria=cat_prevista, score=round(prob, 3), evidencias=[evidencia_clf]
        )
    )
    categorias.sort(key=lambda d: d.score, reverse=True)
    return categorias
