"""
Testes do endpoint de LAUDO e da fusao com laudo (offline, com mocks).

Usamos MockOcrAdapter (nao le PDF de verdade) e ExtractiveSummarizerAdapter (leve,
sem baixar o distilbart) para nao depender de modelos pesados nem de internet.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.ports.factory import get_ocr, get_summarizer
from backend.app.ports.ocr import MockOcrAdapter
from backend.app.ports.summarizer import ExtractiveSummarizerAdapter

client = TestClient(app)

LAUDO_RISCO = (
    "A paciente chora o dia todo e se sente um fracasso desde que o bebe nasceu, "
    "com insonia e muita ansiedade. Exame fisico sem alteracoes."
)


def _override_laudo(texto: str):
    app.dependency_overrides[get_ocr] = lambda: MockOcrAdapter(texto_padrao=texto)
    app.dependency_overrides[get_summarizer] = lambda: ExtractiveSummarizerAdapter()


def test_laudo_analyze_detecta_risco():
    _override_laudo(LAUDO_RISCO)
    try:
        r = client.post(
            "/api/laudo/analyze",
            files={"arquivo": ("laudo.pdf", b"%PDF-fake-bytes", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert b["modalidades"] == ["laudo"]
    assert any(c["categoria"] == "depressao_pos_parto" for c in b["categorias_risco"])
    assert b["texto_documento"] == LAUDO_RISCO
    assert b["resumo"]  # resumo nao vazio
    assert b["backend_ocr"] == "mock"
    assert b["backend_summarizer"] == "extractive"


def test_laudo_rejeita_nao_pdf():
    r = client.post(
        "/api/laudo/analyze",
        files={"arquivo": ("doc.txt", b"x", "text/plain")},
    )
    assert r.status_code == 415


def test_fusion_texto_mais_laudo():
    # texto (violencia) + laudo (pos-parto) -> 2 modalidades, alerta alto
    _override_laudo(LAUDO_RISCO)
    try:
        r = client.post(
            "/api/fusion/analyze",
            data={"texto": "tenho medo dele, ele me empurrou e me ameacou em casa"},
            files={"laudo_arquivo": ("laudo.pdf", b"%PDF", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert set(b["modalidades"]) == {"texto", "laudo"}
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "violencia_domestica" in cats
    assert b["nivel_alerta"] == "alto"
    assert b["resumo"]  # laudo resumido tambem aparece
