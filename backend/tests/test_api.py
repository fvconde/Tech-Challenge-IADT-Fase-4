"""
Testes da API FastAPI (offline).

Para o endpoint de audio, sobrescrevemos a dependencia de transcricao por um
MockTranscriptionAdapter, de modo que nenhum audio e enviado a internet.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.factory import get_transcription
from backend.app.ports.transcription import MockTranscriptionAdapter

client = TestClient(app)


def test_raiz_lista_backends():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert "backends" in body
    assert body["backends"]["nlp"] == "local"


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_text_analyze_violencia():
    resp = client.post(
        "/api/text/analyze",
        json={"texto": "tenho medo dele, ele me empurrou e me ameacou em casa"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["nivel_alerta"] == "alto"
    assert any(c["categoria"] == "violencia_domestica" for c in body["categorias_risco"])


def test_text_analyze_validacao_texto_vazio():
    # texto vazio viola min_length=1 -> 422
    resp = client.post("/api/text/analyze", json={"texto": ""})
    assert resp.status_code == 422


def test_audio_analyze_com_mock():
    # injeta transcricao falsa que devolve um relato de risco
    frase = "choro o dia todo e me sinto um fracasso desde que o bebe nasceu"
    app.dependency_overrides[get_transcription] = lambda: MockTranscriptionAdapter(
        texto_padrao=frase
    )
    try:
        resp = client.post(
            "/api/audio/analyze",
            files={"arquivo": ("consulta.wav", b"RIFF....fake-wav-bytes", "audio/wav")},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["transcricao"] == frase
    assert body["backend_transcricao"] == "mock"
    assert any(
        c["categoria"] == "depressao_pos_parto" for c in body["categorias_risco"]
    )


def test_audio_rejeita_formato_invalido():
    resp = client.post(
        "/api/audio/analyze",
        files={"arquivo": ("consulta.mp3", b"id3fake", "audio/mpeg")},
    )
    assert resp.status_code == 415
