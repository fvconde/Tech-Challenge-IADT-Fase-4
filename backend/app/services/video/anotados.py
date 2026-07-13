"""
Store dos videos ANOTADOS com emocao (gerados por ``anotar_video_emocoes``).

Os videos anotados ficam num diretorio temporario e sao servidos por id (o
router expoe ``GET /api/video/anotado/{video_id}``). Store em memoria (id ->
caminho); simples e suficiente para a demo (some no restart do servidor).

Compartilhado pelo pipeline (grava/registra) e pelo router (serve).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

_DIR_ANOTADOS = Path(tempfile.gettempdir()) / "emocoes_anotadas"
_DIR_ANOTADOS.mkdir(parents=True, exist_ok=True)
_ANOTADOS: dict[str, Path] = {}


def caminho_saida(video_id: str) -> str:
    """Caminho de destino (ainda nao existe) para o video anotado de ``video_id``."""
    return str(_DIR_ANOTADOS / f"{video_id}.mp4")


def registrar(video_id: str, caminho: Path, maximo: int = 12) -> str:
    """Registra o video anotado e limita o acumulo em disco (remove os mais antigos).

    Devolve a URL relativa para baixar/reproduzir o video.
    """
    _ANOTADOS[video_id] = caminho
    while len(_ANOTADOS) > maximo:
        vid_antigo, cam_antigo = next(iter(_ANOTADOS.items()))
        _ANOTADOS.pop(vid_antigo, None)
        try:
            cam_antigo.unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass
    return url_de(video_id)


def caminho_de(video_id: str) -> Path | None:
    """Caminho do video anotado, se ainda existir (nao expirado/servidor reiniciado)."""
    caminho = _ANOTADOS.get(video_id)
    if caminho is None or not caminho.exists():
        return None
    return caminho


def url_de(video_id: str) -> str:
    return f"/api/video/anotado/{video_id}"
