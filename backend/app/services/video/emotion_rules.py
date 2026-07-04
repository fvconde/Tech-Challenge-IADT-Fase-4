"""
Regras de risco para EMOCAO facial (a "customizacao" do caso de uso).

O DeepFace (adapter) devolve a emocao aparente de cada rosto por frame. Aqui
decidimos o que vira RISCO: apenas emocoes NEGATIVAS (tristeza, medo, raiva, nojo)
acima de um limiar de confianca contam, agregadas numa unica categoria
'sinal_emocional_negativo'.

Postura etica: NAO e diagnostico. Emocao aparente != estado clinico; e apenas um
indicio para a equipe observar. Categoria de severidade MEDIA (nao critica).
Contrato comum: retorna list[DeteccaoCategoria] para a fusao.
"""

from __future__ import annotations

from backend.app.ports.base import DeteccaoEmocao
from backend.app.services.text.risk_lexicon import DeteccaoCategoria

# Categoria de risco gerada por emocao negativa sustentada.
CATEGORIA_EMOCAO_NEGATIVA = "sinal_emocional_negativo"

# Emocoes do DeepFace consideradas negativas (proxy de sofrimento/estresse).
EMOCOES_NEGATIVAS = {"sad", "fear", "angry", "disgust"}

# Rotulos legiveis (para as evidencias).
_ROTULO_EMOCAO: dict[str, str] = {
    "sad": "tristeza",
    "fear": "medo",
    "angry": "raiva",
    "disgust": "aversão",
}

# Confianca minima da emocao dominante para contar como indicio.
EMOCAO_SCORE_MIN = 0.4


def avaliar_risco_emocao(
    emocoes: list[DeteccaoEmocao],
    categoria: str = CATEGORIA_EMOCAO_NEGATIVA,
    score_min: float = EMOCAO_SCORE_MIN,
) -> list[DeteccaoCategoria]:
    """
    Converte emocoes faciais em categoria de risco.

    - Considera apenas emocoes NEGATIVAS com score >= score_min.
    - Sem negativas relevantes -> lista vazia.
    - score da categoria = MAIOR confianca entre as emocoes negativas.
    - evidencias = "emocao (score X, frame N)" para rastreabilidade.
    """
    negativas = [
        e for e in emocoes if e.emocao in EMOCOES_NEGATIVAS and e.score >= score_min
    ]
    if not negativas:
        return []

    score = round(min(1.0, max(e.score for e in negativas)), 3)
    evidencias = [
        f"{_ROTULO_EMOCAO.get(e.emocao, e.emocao)} (score {e.score:.2f}, frame {e.frame})"
        for e in negativas
    ]
    return [DeteccaoCategoria(categoria=categoria, score=score, evidencias=evidencias)]
