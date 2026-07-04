"""
Testes do modulo de POSE (100% offline, com MockPoseAdapter).

Nenhum teste carrega o MediaPipe de verdade: usamos sinais "de mentira" para
exercitar as regras de risco e o endpoint, igual ao mock de video/audio.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.base import DeteccaoPose, DeteccaoVisual
from backend.app.ports.factory import get_pose, get_video
from backend.app.ports.pose import MockPoseAdapter
from backend.app.ports.video import MockVideoAdapter
from backend.app.services.video.pose_rules import avaliar_risco_pose

client = TestClient(app)


# --------------------- regras de risco (unidade) ---------------------
def test_risco_pose_agrega_sinais():
    sinais = [
        DeteccaoPose("maos_proximas_ao_rosto", 0.8, 5),
        DeteccaoPose("maos_juntas_ao_corpo", 0.6, 5),
    ]
    cats = avaliar_risco_pose(sinais)
    assert len(cats) == 1
    assert cats[0].categoria == "sinal_corporal_estresse"
    assert cats[0].score == 0.8  # maior confianca entre os sinais
    assert len(cats[0].evidencias) == 2  # rastreabilidade de ambos os sinais


def test_risco_pose_sem_sinais_vazio():
    assert avaliar_risco_pose([]) == []


# --------------------- endpoint /api/video/analyze ---------------------
def _override_video_vazio():
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(deteccoes=[])


def test_video_com_pose_adiciona_modalidade_e_categoria():
    _override_video_vazio()
    app.dependency_overrides[get_pose] = lambda: MockPoseAdapter(
        sinais=[DeteccaoPose("maos_proximas_ao_rosto", 0.7, 3)]
    )
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert "pose" in b["modalidades"]
    assert any(c["categoria"] == "sinal_corporal_estresse" for c in b["categorias_risco"])
    assert b["deteccoes_pose"][0]["sinal"] == "maos_proximas_ao_rosto"
    assert b["backend_pose"] == "mock"
    # categoria de severidade media (nao critica) -> nao vira ALTO sozinha
    assert b["nivel_alerta"] in {"baixo", "medio"}


def test_video_pose_default_mock_nao_interfere():
    # sem override de pose: o default (mock vazio) NAO adiciona a modalidade 'pose'
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("knife", 0.8, 1)]
    )
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    b = r.json()
    assert b["modalidades"] == ["video"]  # comportamento padrao preservado
    assert b["deteccoes_pose"] is None
