"""
Categorizacao por TRECHO (chunk), complementar ao agregado por categoria.

O agregado (DeteccaoCategoria, usado no alerta) resume "quais categorias o
texto todo indica". Este modulo responde a uma pergunta diferente: "qual
FRASE especifica motivou cada indicio, de qual fonte e em que posicao".

Reusa o mesmo lexico de risk_lexicon.py (mesma logica, mesma explicabilidade),
so muda a granularidade: em vez de varrer o texto inteiro, varre frase a
frase. Nao ha dependencia nova nem chamada de rede: e so regex + o lexico ja
existente.
"""

from __future__ import annotations

import re

from backend.app.ports.base import AchadoTrecho
from backend.app.services.text.risk_lexicon import LEXICO_RISCO, normalizar

# Quebra por pontuacao forte (.!?) ou quebra de linha. Mantem frases curtas
# (uma so palavra) fora do resultado para nao gerar ruido.
_SEPARADOR_FRASE = re.compile(r"[.!?\n]+")
_TAMANHO_MINIMO_TRECHO = 3  # caracteres, apos strip


def segmentar(texto: str) -> list[str]:
    """Quebra um texto em trechos (frases/linhas), descartando vazios/curtos demais."""
    if not texto or not texto.strip():
        return []
    partes = _SEPARADOR_FRASE.split(texto)
    return [p.strip() for p in partes if len(p.strip()) >= _TAMANHO_MINIMO_TRECHO]


def detectar_achados(
    texto: str, fonte: str, metadados_base: dict | None = None
) -> list[AchadoTrecho]:
    """
    Segmenta o texto e devolve um AchadoTrecho por (trecho x categoria) em que
    algum gatilho do lexico apareceu. Score = fracao de gatilhos da categoria
    encontrados nesse trecho especifico (mesma saturacao usada no agregado).
    """
    base = dict(metadados_base or {})
    achados: list[AchadoTrecho] = []

    for indice, trecho in enumerate(segmentar(texto)):
        norm = normalizar(trecho)
        for categoria, gatilhos in LEXICO_RISCO.items():
            encontrados = [g for g in gatilhos if g in norm]
            if not encontrados:
                continue
            score = min(1.0, len(encontrados) / 3.0)
            achados.append(
                AchadoTrecho(
                    fonte=fonte,
                    trecho=trecho,
                    categoria=categoria,
                    score=round(score, 3),
                    metadados={**base, "indice_trecho": indice},
                )
            )

    return achados
