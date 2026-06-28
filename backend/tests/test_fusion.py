"""
Testes da FUSAO multimodal: a combinacao de categorias e o endpoint /api/fusion/analyze.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.base import DeteccaoCategoria, DeteccaoVisual
from backend.app.ports.factory import get_video
from backend.app.ports.video import MockVideoAdapter
from backend.app.services.fusion.alerts import (
    BOOST_CORROBORACAO,
    combinar_categorias,
)

client = TestClient(app)


# --------------------- combinar_categorias (unidade) ---------------------
def test_combinar_categorias_corroboracao_multimodal():
    # mesma categoria vista por duas modalidades -> boost + uniao de evidencias
    texto = [DeteccaoCategoria("ansiedade", 0.6, ["texto: ansiosa"])]
    video = [DeteccaoCategoria("ansiedade", 0.5, ["video: sinal X"])]
    comb = combinar_categorias(texto, video)

    assert len(comb) == 1
    c = comb[0]
    assert c.score == round(min(1.0, 0.6 + BOOST_CORROBORACAO), 3)
    assert any("corroboracao" in e for e in c.evidencias)
    assert "texto: ansiosa" in c.evidencias and "video: sinal X" in c.evidencias


def test_combinar_categorias_uniao_simples():
    texto = [DeteccaoCategoria("violencia_domestica", 0.9, ["a"])]
    video = [DeteccaoCategoria("objeto_suspeito_automutilacao", 0.8, ["b"])]
    comb = combinar_categorias(texto, video)
    cats = {c.categoria for c in comb}
    assert cats == {"violencia_domestica", "objeto_suspeito_automutilacao"}


# --------------------- endpoint /api/fusion/analyze ---------------------
def test_fusion_texto_mais_video():
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("knife", 0.8, 3)]
    )
    try:
        r = client.post(
            "/api/fusion/analyze",
            data={"texto": "tenho medo dele, ele me empurrou e me ameacou em casa"},
            files={"video_arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert set(b["modalidades"]) == {"texto", "video"}
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "violencia_domestica" in cats
    assert "objeto_suspeito_automutilacao" in cats
    assert b["nivel_alerta"] == "alto"
    assert b["deteccoes_video"] is not None


def test_fusion_somente_texto():
    r = client.post(
        "/api/fusion/analyze",
        data={"texto": "estou bem e tranquila, consulta de rotina"},
    )
    assert r.status_code == 200
    b = r.json()
    assert b["modalidades"] == ["texto"]
    assert b["nivel_alerta"] == "baixo"


def test_fusion_exige_ao_menos_uma_modalidade():
    r = client.post("/api/fusion/analyze", data={})
    assert r.status_code == 400
