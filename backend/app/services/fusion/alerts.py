"""
Fusao de sinais -> nivel de alerta + acao recomendada.

A fusao trabalha SEMPRE sobre uma lista de DeteccaoCategoria, NAO importa de qual
modalidade ela veio. Isso e proposital: texto/audio e video produzem o mesmo tipo
(DeteccaoCategoria), entao combina-los e so juntar listas. Assim a mesma logica de
alerta serve para 1 modalidade ou para varias (alerta multimodal unico).

Regra de ouro do projeto: o sistema RECOMENDA cuidado / gera alerta para a equipe.
NUNCA diagnostica. Por isso a saida e "acao_recomendada", nao "diagnostico".

------------------------------------------------------------------------------
REGRA DE FUSAO MULTIMODAL (documentada tambem no relatorio-tecnico.md):
1. Junta as categorias de todas as modalidades (texto/audio + video).
2. Categoria repetida em modalidades diferentes -> mantem o MAIOR score, UNE as
   evidencias e aplica um BOOST DE CORROBORACAO (+0.15, saturado em 1.0), porque
   o mesmo risco visto por dois canais e mais confiavel.
3. Categorias CRITICAS (violencia / objeto suspeito) com qualquer indicio -> ALTO.
4. Caso geral: nivel pelo maior score ponderado pela severidade da categoria.
------------------------------------------------------------------------------
"""

from __future__ import annotations

from backend.app.models.schemas import NivelAlerta
from backend.app.ports.base import SentimentResult
from backend.app.services.text.risk_lexicon import (
    PESO_SEVERIDADE,
    DeteccaoCategoria,
)

# Boost aplicado quando a MESMA categoria aparece em 2+ modalidades.
BOOST_CORROBORACAO = 0.15

# Categorias que, com qualquer indicio, ja exigem alerta ALTO.
CATEGORIAS_CRITICAS = {"violencia_domestica", "objeto_suspeito_automutilacao"}

# Marcador (texto) que combinar_categorias escreve nas evidencias quando uma categoria
# e vista em 2+ modalidades. Fonte UNICA: usado tanto para MARCAR quanto para DETECTAR
# corroboracao (ver _corroborada), sem precisar de um novo campo no modelo.
MARCA_CORROBORACAO = "corroboração multimodal"

# Margem de score ponderado para uma categoria NAO-CRITICA "dominar" a acao sobre uma
# critica fraca. 0.30 preserva a demo (objeto real 0.848 vs pos-parto 0.9: diff 0.05),
# so rebaixa criticos genuinamente fracos (ex.: 0.33) a "requer verificacao".
MARGEM_DOMINANCIA = 0.30

# Rotulos legiveis das categorias criticas (para compor o aviso de "requer verificacao").
ROTULO_CATEGORIA: dict[str, str] = {
    "violencia_domestica": "violência doméstica",
    "objeto_suspeito_automutilacao": "objeto suspeito (risco de automutilação)",
}

# Acao recomendada por categoria (texto para a equipe especializada).
ACAO_POR_CATEGORIA: dict[str, str] = {
    "violencia_domestica": (
        "ALERTA PRIORITÁRIO: indícios de violência doméstica. Acionar protocolo "
        "institucional de violência, oferecer escuta protegida e privada, e acionar "
        "serviço social/segurança conforme fluxo. NÃO confrontar acompanhante."
    ),
    "objeto_suspeito_automutilacao": (
        "ALERTA PRIORITÁRIO: objeto potencialmente perigoso detectado no vídeo "
        "(proxy de risco de automutilação). Acionar avaliação de segurança e saúde "
        "mental, garantir ambiente seguro e revisar o(s) frame(s) sinalizado(s)."
    ),
    "depressao_pos_parto": (
        "Encaminhar para avaliação em saúde mental perinatal (psicologia/psiquiatria). "
        "Aplicar instrumento de rastreio (ex.: EPDS) com a equipe."
    ),
    "ansiedade": (
        "Sinalizar à equipe para acolhimento e avaliação de quadro ansioso; "
        "considerar apoio psicológico."
    ),
    "fadiga_hormonal": (
        "Sugerir avaliação clínica/hormonal pela equipe (investigar causas de fadiga)."
    ),
    "sinal_emocional_negativo": (
        "Vídeo indica emoção facial negativa aparente (tristeza/medo/raiva). "
        "Sinalizar à equipe para acolhimento e escuta ativa; NÃO é diagnóstico, "
        "apenas um indício a ser observado no contexto da consulta."
    ),
    "sinal_corporal_estresse": (
        "Vídeo indica sinais corporais de tensão/proteção (postura/gestos). "
        "Sinalizar à equipe para observação e escuta acolhedora; NÃO é diagnóstico, "
        "apenas um indício comportamental a ser considerado com cautela."
    ),
}

ACAO_SEM_RISCO = (
    "Sem indícios de risco relevantes nesta análise. Manter acompanhamento de rotina."
)


def combinar_categorias(
    *listas: list[DeteccaoCategoria],
) -> list[DeteccaoCategoria]:
    """
    Combina varias listas de categorias (uma por modalidade) em uma so.

    Para a mesma categoria vista em modalidades diferentes:
      - score final = max(scores) + BOOST_CORROBORACAO (saturado em 1.0);
      - evidencias = uniao das evidencias.
    Se a categoria aparece em uma unica lista, fica como esta.
    """
    # quantas listas (modalidades) mencionaram cada categoria
    ocorrencias: dict[str, int] = {}
    combinadas: dict[str, DeteccaoCategoria] = {}

    for lista in listas:
        # evita contar 2x a mesma categoria dentro da MESMA modalidade
        categorias_desta_lista: set[str] = set()
        for det in lista:
            if det.categoria not in combinadas:
                # copia para nao mutar o objeto original
                combinadas[det.categoria] = DeteccaoCategoria(
                    categoria=det.categoria,
                    score=det.score,
                    evidencias=list(det.evidencias),
                )
            else:
                alvo = combinadas[det.categoria]
                alvo.score = max(alvo.score, det.score)
                alvo.evidencias.extend(det.evidencias)
            categorias_desta_lista.add(det.categoria)

        for cat in categorias_desta_lista:
            ocorrencias[cat] = ocorrencias.get(cat, 0) + 1

    # aplica o boost de corroboracao nas categorias vistas em 2+ modalidades
    for cat, n in ocorrencias.items():
        if n >= 2:
            d = combinadas[cat]
            d.score = round(min(1.0, d.score + BOOST_CORROBORACAO), 3)
            d.evidencias.append(f"{MARCA_CORROBORACAO} ({n} modalidades)")

    resultado = list(combinadas.values())
    resultado.sort(key=lambda d: d.score, reverse=True)
    return resultado


def _corroborada(categoria: DeteccaoCategoria) -> bool:
    """True se a categoria foi corroborada por 2+ modalidades (marca de combinar_categorias)."""
    return any(MARCA_CORROBORACAO in e for e in categoria.evidencias)


def avaliar_alerta(
    categorias: list[DeteccaoCategoria],
    sentimento: SentimentResult,
) -> tuple[NivelAlerta, str]:
    """
    Decide o nivel de alerta e a acao recomendada a partir das categorias (ja
    combinadas, se multimodal) e do sentimento.

    - Categoria critica com qualquer indicio -> sempre ALTO.
    - Caso geral: usa o maior score ponderado pela severidade da categoria.
    - Sem categorias, mas sentimento muito negativo -> MEDIO (acolhimento).
    """
    if not categorias:
        if sentimento.score <= -0.5:
            return (
                NivelAlerta.medio,
                "Sentimento predominantemente negativo, sem categoria específica. "
                "Recomenda-se acolhimento e escuta ativa pela equipe.",
            )
        return NivelAlerta.baixo, ACAO_SEM_RISCO

    def ponderado(c: DeteccaoCategoria) -> float:
        return c.score * PESO_SEVERIDADE.get(c.categoria, 0.5)

    # categoria de maior score ponderado pela severidade (define a acao "principal")
    top = max(categorias, key=ponderado)
    acao = ACAO_POR_CATEGORIA.get(top.categoria, ACAO_SEM_RISCO)

    # Categorias criticas: qualquer indicio -> nivel ALTO (regra de seguranca; NAO muda).
    # A ACAO, porem, considera score E corroboracao: uma critica FRACA (baixo score, sem
    # corroboracao) nao deve dominar o texto quando ha nao-critica MUITO mais forte.
    criticas = [c for c in categorias if c.categoria in CATEGORIAS_CRITICAS]
    if criticas:
        critica_top = max(criticas, key=ponderado)
        nao_criticas = [c for c in categorias if c.categoria not in CATEGORIAS_CRITICAS]
        top_nc = max(nao_criticas, key=ponderado) if nao_criticas else None

        # Uma nao-critica "domina" a acao quando e significativamente mais forte
        # (score ponderado) E corroborada, enquanto a critica NAO tem corroboracao.
        domina = (
            top_nc is not None
            and ponderado(top_nc) >= ponderado(critica_top) + MARGEM_DOMINANCIA
            and _corroborada(top_nc)
            and not _corroborada(critica_top)
        )
        if domina:
            rotulo = ROTULO_CATEGORIA.get(critica_top.categoria, critica_top.categoria)
            acao_composta = (
                f"{ACAO_POR_CATEGORIA.get(top_nc.categoria, ACAO_SEM_RISCO)} "
                f"Observação: há também indício de {rotulo} de baixa confiança "
                f"(score {critica_top.score:.2f}, sem corroboração) — requer verificação "
                f"pela equipe, não confirma risco isoladamente."
            )
            return NivelAlerta.alto, acao_composta
        # Caso geral: a critica domina a acao prioritaria (comportamento anterior).
        return NivelAlerta.alto, ACAO_POR_CATEGORIA[critica_top.categoria]

    risco = ponderado(top)
    if risco >= 0.6:
        nivel = NivelAlerta.alto
    elif risco >= 0.3:
        nivel = NivelAlerta.medio
    else:
        nivel = NivelAlerta.baixo
    return nivel, acao
