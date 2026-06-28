"""
Fusao de sinais -> nivel de alerta + acao recomendada.

Nesta Sessao 1 a "fusao" combina os sinais de TEXTO (categorias de risco do lexico
+ sentimento). Em sessoes futuras esta mesma camada recebera tambem sinais de VIDEO
(YOLOv8/DeepFace/pose) para um alerta multimodal unico.

Regra de ouro do projeto: o sistema RECOMENDA cuidado / gera alerta para a equipe.
NUNCA diagnostica. Por isso a saida e "acao_recomendada", nao "diagnostico".
"""

from __future__ import annotations

from backend.app.models.schemas import NivelAlerta
from backend.app.ports.base import SentimentResult
from backend.app.services.text.risk_lexicon import (
    PESO_SEVERIDADE,
    DeteccaoCategoria,
)

# Acao recomendada por categoria (texto para a equipe especializada).
ACAO_POR_CATEGORIA: dict[str, str] = {
    "violencia_domestica": (
        "ALERTA PRIORITARIO: indicios de violencia domestica. Acionar protocolo "
        "institucional de violencia, oferecer escuta protegida e privada, e acionar "
        "servico social/seguranca conforme fluxo. NAO confrontar acompanhante."
    ),
    "depressao_pos_parto": (
        "Encaminhar para avaliacao em saude mental perinatal (psicologia/psiquiatria). "
        "Aplicar instrumento de rastreio (ex.: EPDS) com a equipe."
    ),
    "ansiedade": (
        "Sinalizar a equipe para acolhimento e avaliacao de quadro ansioso; "
        "considerar apoio psicologico."
    ),
    "fadiga_hormonal": (
        "Sugerir avaliacao clinica/hormonal pela equipe (investigar causas de fadiga)."
    ),
}

ACAO_SEM_RISCO = (
    "Sem indicios de risco relevantes nesta analise. Manter acompanhamento de rotina."
)


def avaliar_alerta(
    categorias: list[DeteccaoCategoria],
    sentimento: SentimentResult,
) -> tuple[NivelAlerta, str]:
    """
    Decide o nivel de alerta e a acao recomendada.

    - Violencia domestica com qualquer indicio -> sempre ALTO.
    - Caso geral: usa o maior score ponderado pela severidade da categoria.
    - Sem categorias, mas sentimento muito negativo -> MEDIO (acolhimento).
    """
    if not categorias:
        if sentimento.score <= -0.5:
            return (
                NivelAlerta.medio,
                "Sentimento predominantemente negativo, sem categoria especifica. "
                "Recomenda-se acolhimento e escuta ativa pela equipe.",
            )
        return NivelAlerta.baixo, ACAO_SEM_RISCO

    # categoria de maior score ponderado pela severidade
    def ponderado(c: DeteccaoCategoria) -> float:
        return c.score * PESO_SEVERIDADE.get(c.categoria, 0.5)

    top = max(categorias, key=ponderado)
    acao = ACAO_POR_CATEGORIA.get(top.categoria, ACAO_SEM_RISCO)

    # violencia: sempre alto
    if any(c.categoria == "violencia_domestica" for c in categorias):
        return NivelAlerta.alto, ACAO_POR_CATEGORIA["violencia_domestica"]

    risco = ponderado(top)
    if risco >= 0.6:
        nivel = NivelAlerta.alto
    elif risco >= 0.3:
        nivel = NivelAlerta.medio
    else:
        nivel = NivelAlerta.baixo
    return nivel, acao
