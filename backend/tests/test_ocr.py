"""
Testes de OCR/extracao de PDF.

O teste do LocalOcrAdapter gera um PDF REAL (reportlab) e extrai com pdfplumber.
Se as libs nao estiverem instaladas, o teste e pulado (importorskip).
"""

from __future__ import annotations

import pytest

from backend.app.ports.ocr import LocalOcrAdapter, MockOcrAdapter


def test_local_ocr_extrai_texto_de_pdf(tmp_path):
    pytest.importorskip("reportlab")
    pytest.importorskip("pdfplumber")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = tmp_path / "laudo.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawString(80, 760, "Paciente refere choro e ansiedade no pos-parto.")
    c.drawString(80, 740, "Exame fisico sem alteracoes significativas.")
    c.save()

    resultado = LocalOcrAdapter().extrair_texto(str(pdf))
    assert "ansiedade" in resultado.texto.lower()
    assert resultado.paginas == 1
    assert resultado.backend in ("pdfplumber", "pymupdf")
    assert resultado.usou_ocr is False


def test_mock_ocr_le_txt_irmao(tmp_path):
    (tmp_path / "doc.txt").write_text("texto do laudo sintetico", encoding="utf-8")
    resultado = MockOcrAdapter().extrair_texto(str(tmp_path / "doc.pdf"))
    assert resultado.texto == "texto do laudo sintetico"
    assert resultado.backend == "mock"
