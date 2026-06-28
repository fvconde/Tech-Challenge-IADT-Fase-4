"""
Endpoints de analise de VIDEO (placeholder da Sessao 1).

O requisito YOLOv8 e demonstrado, nesta entrega, no notebook
notebooks/01_yolov8_demo.ipynb. A integracao via API (atras de um VideoPort,
alimentando a fusao) entra na proxima sessao. Este endpoint existe para deixar
o contrato REST visivel e responder de forma honesta enquanto isso.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/video", tags=["video"])


@router.get("/status")
def status() -> dict:
    """Informa o estado do modulo de video."""
    return {
        "modulo": "video",
        "status": "demo_em_notebook",
        "detalhe": (
            "Deteccao YOLOv8 disponivel em notebooks/01_yolov8_demo.ipynb. "
            "Endpoint de inferencia sera adicionado na proxima sessao."
        ),
    }
