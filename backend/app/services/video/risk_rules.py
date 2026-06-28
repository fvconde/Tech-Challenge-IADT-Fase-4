"""
Regras de risco para VIDEO (a "customizacao" do nosso caso de uso).

O modelo YOLOv8 e generico (classes COCO). A especializacao para saude/seguranca
da mulher acontece AQUI, no pos-processamento: decidimos quais classes detectadas
representam risco e em qual categoria elas caem.

Padrao atual: classes-foco (ex.: 'knife', 'scissors') -> categoria
'objeto_suspeito_automutilacao'. As classes-foco sao configuraveis (.env), entao
trocar o alvo no futuro NAO exige mexer no modelo.

O retorno e uma lista de DeteccaoCategoria -- O MESMO tipo que o texto produz --
para que a camada de fusao trate todas as modalidades de forma uniforme.
"""

from __future__ import annotations

from backend.app.ports.base import DeteccaoVisual
from backend.app.services.text.risk_lexicon import DeteccaoCategoria

# Categoria de risco gerada quando uma classe-foco e detectada no video.
CATEGORIA_OBJETO_SUSPEITO = "objeto_suspeito_automutilacao"


def avaliar_risco_visual(
    deteccoes: list[DeteccaoVisual],
    classes_foco: list[str],
    categoria: str = CATEGORIA_OBJETO_SUSPEITO,
) -> list[DeteccaoCategoria]:
    """
    Converte deteccoes visuais em categorias de risco.

    - Filtra apenas as deteccoes cujas classes estao em 'classes_foco'.
    - score da categoria = MAIOR confianca entre as deteccoes-foco.
    - evidencias = lista legivel "classe (conf X, frame N)" -> rastreabilidade.
    - Sem deteccoes-foco -> lista vazia (nenhum risco visual).
    """
    foco = {c.lower() for c in classes_foco}
    relevantes = [d for d in deteccoes if d.classe.lower() in foco]
    if not relevantes:
        return []

    score = round(min(1.0, max(d.confianca for d in relevantes)), 3)
    evidencias = [
        f"{d.classe} (conf {d.confianca:.2f}, frame {d.frame})" for d in relevantes
    ]
    return [DeteccaoCategoria(categoria=categoria, score=score, evidencias=evidencias)]
