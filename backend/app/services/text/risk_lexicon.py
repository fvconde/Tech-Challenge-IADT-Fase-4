"""
Deteccao de categorias de risco por LEXICO (regras transparentes).

Cada categoria tem uma lista de termos/expressoes-gatilho (em PT-BR, normalizados
sem acento). Quando uma expressao aparece no texto, ela vira uma "evidencia" e
soma no score da categoria. Essa abordagem e proposital:

  -> EXPLICABILIDADE: para apoio a decisao clinica, a equipe precisa ver POR QUE
     o sistema levantou um alerta. Cada alerta carrega as expressoes que o motivaram.

O score final por categoria fica em [0, 1] (saturado). Um classificador estatistico
(services/text/classifier.py) complementa este lexico.
"""

from __future__ import annotations

import unicodedata

# DeteccaoCategoria mora na camada de dominio (ports/base.py) porque e compartilhada
# por texto, audio e video. Reexportamos aqui para nao quebrar imports existentes.
from backend.app.ports.base import DeteccaoCategoria

__all__ = ["DeteccaoCategoria", "normalizar", "detectar_categorias",
           "LEXICO_RISCO", "PESO_SEVERIDADE"]


def normalizar(texto: str) -> str:
    """Minuscula + remove acentos (mesma normalizacao usada nos lexicos)."""
    texto = texto.lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Expressoes-gatilho por categoria (ja sem acento).
# Peso por categoria: violencia tem peso maior (1 indicio ja e relevante).
LEXICO_RISCO: dict[str, list[str]] = {
    "depressao_pos_parto": [
        "choro o dia todo", "nao paro de chorar", "me sinto um fracasso", "fracasso",
        "nao sinto amor pelo bebe", "nao consigo cuidar do bebe", "me sinto vazia",
        "sem vontade de nada", "nao tenho esperanca", "me sinto inutil", "culpa",
        "vontade de sumir", "arrependida de ter tido", "exausta e triste",
    ],
    "ansiedade": [
        "ansiosa", "ansiedade", "coracao acelerado", "muito preocupada", "nervosa",
        "ataque de panico", "panico", "aperto no peito", "falta de ar", "sem ar",
        "nao consigo relaxar", "pensamentos acelerados", "insonia",
    ],
    "violencia_domestica": [
        "ele me bateu", "apanhei", "me empurrou", "me ameacou", "tenho medo dele",
        "ele me controla", "nao posso sair de casa", "ele grita comigo",
        "ele me machucou", "tenho vergonha de contar", "ele me proibe",
        "fico com medo em casa", "ele me xinga",
    ],
    "fadiga_hormonal": [
        "cansada o tempo todo", "fadiga", "sem energia", "ondas de calor",
        "alteracao de humor", "menstruacao irregular", "muito cansaco",
        "calores", "sem disposicao", "exausta",
    ],
}

# Peso de severidade por categoria (influencia o nivel de alerta na fusao).
# Inclui tambem categorias que vem de outras modalidades (ex.: video), pois a
# fusao trata todas como o mesmo tipo DeteccaoCategoria.
PESO_SEVERIDADE: dict[str, float] = {
    "violencia_domestica": 1.0,   # qualquer indicio ja exige atencao maxima
    "objeto_suspeito_automutilacao": 1.0,  # categoria de VIDEO (proxy automutilacao)
    "depressao_pos_parto": 0.9,
    "ansiedade": 0.6,
    "sinal_emocional_negativo": 0.6,  # VIDEO/emocao (DeepFace) - proxy, nao critica
    "sinal_corporal_estresse": 0.5,   # VIDEO/pose (MediaPipe) - proxy, nao critica
    "fadiga_hormonal": 0.5,
}


def detectar_categorias(texto: str) -> list[DeteccaoCategoria]:
    """
    Varre o texto e devolve as categorias de risco com indicios encontrados.

    score = saturacao de (qtd_evidencias / 3). Ou seja, 3+ expressoes -> 1.0.
    Categorias sem nenhuma evidencia nao entram no resultado.
    """
    norm = normalizar(texto)
    resultados: list[DeteccaoCategoria] = []

    for categoria, gatilhos in LEXICO_RISCO.items():
        evidencias = [g for g in gatilhos if g in norm]
        if not evidencias:
            continue
        score = min(1.0, len(evidencias) / 3.0)
        resultados.append(
            DeteccaoCategoria(categoria=categoria, score=round(score, 3), evidencias=evidencias)
        )

    # ordena da categoria mais "intensa" para a menos
    resultados.sort(key=lambda d: d.score, reverse=True)
    return resultados
