"""
Testes do modulo de EMOCAO facial (100% offline, com MockEmotionAdapter).

Nenhum teste carrega o DeepFace de verdade: usamos emocoes "de mentira" para
exercitar as regras de risco e o endpoint multimodal.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.base import DeteccaoEmocao, DeteccaoVisual
from backend.app.ports.emotion import MockEmotionAdapter
from backend.app.ports.factory import get_emotion, get_video
from backend.app.ports.video import MockVideoAdapter
from backend.app.services.video.emotion_rules import avaliar_risco_emocao

client = TestClient(app)


# --------------------- regras de risco (unidade) ---------------------
def test_risco_emocao_negativa_gera_categoria():
    cats = avaliar_risco_emocao([DeteccaoEmocao("sad", 0.7, 2)])
    assert len(cats) == 1
    assert cats[0].categoria == "sinal_emocional_negativo"
    assert cats[0].score == 0.7
    assert cats[0].evidencias


def test_risco_emocao_positiva_ignorada():
    assert avaliar_risco_emocao([DeteccaoEmocao("happy", 0.95, 0)]) == []


def test_risco_emocao_abaixo_do_limiar_ignorada():
    # negativa, mas com score fraco (< EMOCAO_SCORE_MIN) -> nao conta
    assert avaliar_risco_emocao([DeteccaoEmocao("fear", 0.2, 0)]) == []


# --------------------- endpoint /api/video/analyze ---------------------
def test_video_com_emocao_negativa_adiciona_modalidade():
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(deteccoes=[])
    app.dependency_overrides[get_emotion] = lambda: MockEmotionAdapter(
        emocoes=[DeteccaoEmocao("fear", 0.6, 1)]
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
    assert "emocao" in b["modalidades"]
    assert any(c["categoria"] == "sinal_emocional_negativo" for c in b["categorias_risco"])
    assert b["deteccoes_emocao"][0]["emocao"] == "fear"
    assert b["backend_emocao"] == "mock"


def test_video_emocao_positiva_presente_sem_categoria():
    # rosto detectado, emocao so positiva: modalidade 'emocao' presente, sem risco
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(deteccoes=[])
    app.dependency_overrides[get_emotion] = lambda: MockEmotionAdapter(
        emocoes=[DeteccaoEmocao("happy", 0.9, 0)]
    )
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("foto.jpg", b"fake-img", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    b = r.json()
    assert "emocao" in b["modalidades"]
    assert not any(
        c["categoria"] == "sinal_emocional_negativo" for c in b["categorias_risco"]
    )


def test_video_objeto_critico_e_emocao_coexistem():
    # YOLO com objeto critico (knife) + emocao negativa: categorias distintas,
    # sem falsa corroboracao; objeto critico mantem o alerta ALTO.
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("knife", 0.85, 4)]
    )
    app.dependency_overrides[get_emotion] = lambda: MockEmotionAdapter(
        emocoes=[DeteccaoEmocao("sad", 0.7, 4)]
    )
    try:
        r = client.post(
            "/api/video/analyze",
            files={"arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    b = r.json()
    assert set(b["modalidades"]) == {"video", "emocao"}
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "objeto_suspeito_automutilacao" in cats
    assert "sinal_emocional_negativo" in cats
    assert b["nivel_alerta"] == "alto"  # objeto critico
