"""
Adapters de OCR/extracao de texto de PDF (OcrPort).

- LocalOcrAdapter: extracao 100% LOCAL, em cascata:
    1) pdfplumber  (default; otimo para PDFs com texto "de verdade");
    2) PyMuPDF/fitz (fallback se o pdfplumber vier vazio ou falhar);
    3) pytesseract (OCR) SO se o PDF for imagem/escaneado (texto ainda vazio).
  Todos os imports sao preguicosos (lazy), entao o app sobe mesmo sem essas libs.
  *** NUNCA usamos Amazon Textract *** (bloqueado no Free Plan; ver CLAUDE.md).

- MockOcrAdapter: nao le PDF. Devolve um texto fixo ou o conteudo de um .txt
  "irmao" do PDF. Serve para testes/offline (igual aos outros mocks).

Por que cascata? Robustez sem custo: a maioria dos laudos digitais tem texto
selecionavel (pdfplumber resolve). Só caímos no OCR (mais lento) quando o PDF é
uma imagem escaneada.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.ports.base import OcrPort, OcrResult

logger = logging.getLogger(__name__)

# Abaixo deste tamanho consideramos que "nao ha texto extraivel" e tentamos o proximo
# metodo. PDFs de imagem costumam devolver string vazia ou quase isso.
MIN_CARACTERES = 10


class LocalOcrAdapter(OcrPort):
    """Extrai texto de PDF localmente, em cascata pdfplumber -> PyMuPDF -> OCR."""

    def extrair_texto(self, caminho_pdf: str) -> OcrResult:
        # 1) pdfplumber
        resultado = self._tentar_pdfplumber(caminho_pdf)
        if resultado and len(resultado.texto.strip()) >= MIN_CARACTERES:
            return resultado

        # 2) PyMuPDF (fitz)
        resultado = self._tentar_pymupdf(caminho_pdf)
        if resultado and len(resultado.texto.strip()) >= MIN_CARACTERES:
            return resultado

        # 3) OCR (pytesseract) - PDF provavelmente e imagem/escaneado
        resultado = self._tentar_ocr(caminho_pdf)
        if resultado is not None:
            return resultado

        # nada funcionou: devolve vazio (a camada de cima decide o que fazer)
        logger.warning("Nenhum metodo extraiu texto de %s", caminho_pdf)
        return OcrResult(texto="", paginas=0, backend="nenhum", usou_ocr=False)

    # ----------------------- pdfplumber -----------------------
    def _tentar_pdfplumber(self, caminho: str) -> OcrResult | None:
        try:
            import pdfplumber  # lazy
        except ImportError:
            logger.info("pdfplumber indisponivel; pulando.")
            return None
        try:
            partes: list[str] = []
            with pdfplumber.open(caminho) as pdf:
                for pagina in pdf.pages:
                    partes.append(pagina.extract_text() or "")
                n = len(pdf.pages)
            return OcrResult(texto="\n".join(partes).strip(), paginas=n, backend="pdfplumber")
        except Exception as exc:  # pragma: no cover - PDF corrompido etc.
            logger.warning("pdfplumber falhou: %s", exc)
            return None

    # ----------------------- PyMuPDF -----------------------
    def _tentar_pymupdf(self, caminho: str) -> OcrResult | None:
        try:
            import fitz  # PyMuPDF (lazy)
        except ImportError:
            logger.info("PyMuPDF indisponivel; pulando.")
            return None
        try:
            partes: list[str] = []
            with fitz.open(caminho) as doc:
                for pagina in doc:
                    partes.append(pagina.get_text() or "")
                n = doc.page_count
            return OcrResult(texto="\n".join(partes).strip(), paginas=n, backend="pymupdf")
        except Exception as exc:  # pragma: no cover
            logger.warning("PyMuPDF falhou: %s", exc)
            return None

    # ----------------------- OCR (pytesseract) -----------------------
    def _tentar_ocr(self, caminho: str) -> OcrResult | None:
        """Renderiza cada pagina como imagem (via PyMuPDF) e roda Tesseract."""
        try:
            import fitz  # para rasterizar o PDF
            import pytesseract  # lazy
            from PIL import Image  # lazy
        except ImportError:
            logger.info("Stack de OCR (pytesseract/PIL/PyMuPDF) indisponivel; pulando.")
            return None
        try:
            import io

            partes: list[str] = []
            with fitz.open(caminho) as doc:
                for pagina in doc:
                    pix = pagina.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    partes.append(pytesseract.image_to_string(img, lang="por"))
                n = doc.page_count
            return OcrResult(
                texto="\n".join(partes).strip(), paginas=n,
                backend="pytesseract", usou_ocr=True,
            )
        except Exception as exc:  # pragma: no cover - tesseract ausente etc.
            logger.warning("OCR (pytesseract) falhou: %s", exc)
            return None


class MockOcrAdapter(OcrPort):
    """OCR falso para testes/offline (le um .txt irmao do PDF ou texto padrao)."""

    def __init__(self, texto_padrao: str = "laudo sintetico para teste") -> None:
        self.texto_padrao = texto_padrao

    def extrair_texto(self, caminho_pdf: str) -> OcrResult:
        gemeo_txt = Path(caminho_pdf).with_suffix(".txt")
        if gemeo_txt.exists():
            texto = gemeo_txt.read_text(encoding="utf-8").strip()
        else:
            texto = self.texto_padrao
        return OcrResult(texto=texto, paginas=1, backend="mock")
