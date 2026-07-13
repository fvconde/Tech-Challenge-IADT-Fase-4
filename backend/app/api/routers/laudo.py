"""Endpoint de analise de LAUDO (documento PDF)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import NlpPort, OcrPort, StoragePort, SummarizerPort
from backend.app.ports.factory import (
    get_nlp,
    get_ocr,
    get_storage,
    get_summarizer,
)
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.text.document import analisar_laudo

router = APIRouter(prefix="/api/laudo", tags=["laudo"])

EXTENSOES_SUPORTADAS = {".pdf"}


def _sufixo(nome: str) -> str:
    return "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""


@router.post(
    "/analyze", response_model=AnaliseRiscoResponse, summary="Analisar laudo em PDF"
)
async def analisar(
    arquivo: UploadFile = File(..., description="PDF de laudo/exame"),
    ocr: OcrPort = Depends(get_ocr),
    nlp: NlpPort = Depends(get_nlp),
    summarizer: SummarizerPort = Depends(get_summarizer),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Extrai texto de um PDF de laudo, analisa risco e resume.

    O laudo entra na MESMA fusao multimodal (como modalidade 'laudo'). Extracao de
    texto e 100% local (pdfplumber/PyMuPDF/OCR) -- NUNCA Textract.
    """
    nome = arquivo.filename or "laudo.pdf"
    if _sufixo(nome) not in EXTENSOES_SUPORTADAS:
        raise HTTPException(status_code=415, detail="Envie um arquivo PDF.")

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    resultado = analisar_laudo(
        nome_arquivo=nome,
        conteudo=conteudo,
        ocr=ocr,
        nlp=nlp,
        summarizer=summarizer,
        storage=storage,
    )

    if not resultado.ocr.texto.strip():
        raise HTTPException(
            status_code=422,
            detail="Nao foi possivel extrair texto do PDF (documento vazio ou imagem sem OCR).",
        )

    # monta o alerta via fusao (modalidade unica: laudo)
    backend_sum = getattr(summarizer, "nome_backend", None) if resultado.resumo else None
    return fundir(
        categorias_laudo=resultado.categorias,
        nlp_laudo=resultado.nlp,
        achados=resultado.achados,
        texto_documento=resultado.ocr.texto,
        resumo=resultado.resumo,
        backend_ocr=resultado.ocr.backend,
        backend_summarizer=backend_sum,
    )
