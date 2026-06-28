"""
Testes do modulo de VIDEO (100% offline, com MockVideoAdapter).

Nenhum teste carrega o YOLO de verdade: usamos deteccoes "de mentira" para exercitar
as regras de risco e o endpoint, igual fizemos com o mock de audio na Sessao 1.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.base import DeteccaoVisual
from backend.app.ports.factory import get_video
from backend.app.ports.video import MockVideoAdapter
from backend.app.services.video.risk_rules import avaliar_risco_visual

client = TestClient(app)


# --------------------- regras de risco (unidade) ---------------------
def test_risco_visual_detecta_classe_foco():
    dets = [DeteccaoVisual("knife", 0.82, 10), DeteccaoVisual("person", 0.95, 10)]
    cats = avaliar_risco_visual(dets, ["knife", "scissors"])
    assert len(cats) == 1
    assert cats[0].categoria == "objeto_suspeito_automutilacao"
    assert cats[0].score == 0.82  # maior confianca entre as classes-foco
    assert cats[0].evidencias  # tem rastreabilidade


def test_risco_visual_ignora_classes_fora_do_foco():
    dets = [DeteccaoVisual("person", 0.95, 0), DeteccaoVisual("bus", 0.9, 0)]
    assert avaliar_risco_visual(dets, ["knife", "scissors"]) == []


# --------------------- endpoint /api/video/analyze ---------------------
def _override_video(deteccoes, frames=1):
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=deteccoes, frames_analisados=frames
    )


def test_video_analyze_objeto_suspeito_gera_alto():
    _override_video([DeteccaoVisual("scissors", 0.7, 12)], frames=5)
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert b["nivel_alerta"] == "alto"
    assert b["modalidades"] == ["video"]
    assert any(
        c["categoria"] == "objeto_suspeito_automutilacao" for c in b["categorias_risco"]
    )
    assert b["deteccoes_video"][0]["classe"] == "scissors"
    assert b["frames_analisados"] == 5
    assert b["backend_video"] == "mock"


def test_video_analyze_sem_objeto_foco_fica_baixo():
    _override_video([DeteccaoVisual("person", 0.9, 0)])
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("foto.jpg", b"fake-img", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    b = r.json()
    assert b["nivel_alerta"] == "baixo"
    assert b["categorias_risco"] == []


def test_video_formato_invalido():
    r = client.post(
        "/api/video/analyze",
        files={"arquivo": ("doc.txt", b"x", "text/plain")},
    )
    assert r.status_code == 415
