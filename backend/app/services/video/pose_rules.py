"""
Regras de risco para POSE/atividade corporal (a "customizacao" do caso de uso).

O MediaPipe (adapter) devolve SINAIS observaveis (ex.: maos proximas ao rosto,
maos juntas ao corpo). Aqui decidimos como esses sinais viram RISCO: agregamos os
sinais numa unica categoria 'sinal_corporal_estresse' (proxy conservador de
estresse/defesa), com score e evidencias rastreaveis.

Postura etica: NAO e diagnostico. Categoria de severidade MEDIA (nao critica) --
serve para a equipe observar, nunca para concluir sozinha. Mesmo contrato dos
outros modulos: retorna list[DeteccaoCategoria] para a fusao tratar tudo igual.
"""

from __future__ import annotations

from backend.app.ports.base import DeteccaoPose
from backend.app.services.text.risk_lexicon import DeteccaoCategoria

# Categoria de risco gerada quando ha sinais corporais de estresse/defesa.
CATEGORIA_SINAL_CORPORAL = "sinal_corporal_estresse"

# Rotulos legiveis dos sinais (para as evidencias).
_ROTULO_SINAL: dict[str, str] = {
    "maos_proximas_ao_rosto": "mãos próximas ao rosto (gesto de proteção)",
    "maos_juntas_ao_corpo": "mãos juntas ao corpo (autoconforto/ansiedade)",
}


def avaliar_risco_pose(
    sinais: list[DeteccaoPose],
    categoria: str = CATEGORIA_SINAL_CORPORAL,
) -> list[DeteccaoCategoria]:
    """
    Converte sinais corporais em categoria de risco.

    - Sem sinais -> lista vazia (nenhum risco corporal).
    - score da categoria = MAIOR confianca entre os sinais.
    - evidencias = "rotulo (conf X, frame N)" para rastreabilidade.
    """
    if not sinais:
        return []

    score = round(min(1.0, max(s.confianca for s in sinais)), 3)
    evidencias = [
        f"{_ROTULO_SINAL.get(s.sinal, s.sinal)} (conf {s.confianca:.2f}, frame {s.frame})"
        for s in sinais
    ]
    return [DeteccaoCategoria(categoria=categoria, score=score, evidencias=evidencias)]
