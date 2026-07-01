"""
Endpoint de FUSAO MULTIMODAL.

Recebe texto, video e/ou laudo (PDF) e devolve UM unico alerta combinando as
modalidades. Demonstra o coracao do desafio: fundir sinais de diferentes tipos de dado.

Como aceita upload de arquivos + campo de texto, usa multipart/form-data
(parametros Form/File), e nao JSON.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.api.routers.laudo import (
    EXTENSOES_SUPORTADAS as EXT_LAUDO,
)
from backend.app.api.routers.video import EXTENSOES_SUPORTADAS, _sufixo
from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import (
    NlpPort,
    OcrPort,
    StoragePort,
    SummarizerPort,
    VideoPort,
)
from backend.app.ports.factory import (
    get_nlp,
    get_ocr,
    get_storage,
    get_summarizer,
    get_video,
)
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.text.document import analisar_laudo
from backend.app.services.text.nlp import extrair_categorias_e_nlp
from backend.app.services.video.pipeline import analisar_video

router = APIRouter(prefix="/api/fusion", tags=["fusao"])


@router.post(
    "/analyze",
    response_model=AnaliseRiscoResponse,
    summary="Análise multimodal (fusão)",
)
async def analisar(
    texto: str | None = Form(default=None, description="Relato/transcricao (opcional)"),
    video_arquivo: UploadFile | None = File(
        default=None, description="Video ou imagem clinica (opcional)"
    ),
    laudo_arquivo: UploadFile | None = File(
        default=None, description="PDF de laudo (opcional)"
    ),
    nlp: NlpPort = Depends(get_nlp),
    video: VideoPort = Depends(get_video),
    ocr: OcrPort = Depends(get_ocr),
    summarizer: SummarizerPort = Depends(get_summarizer),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Funde texto + video + laudo em um alerta unico.

    Pelo menos UMA das modalidades deve ser enviada. Quando duas (ou mais) apontam
    o mesmo risco, a fusao aplica boost de corroboracao (ver services/fusion/alerts.py).
    """
    tem_texto = bool(texto and texto.strip())
    tem_video = video_arquivo is not None and bool(video_arquivo.filename)
    tem_laudo = laudo_arquivo is not None and bool(laudo_arquivo.filename)
    if not (tem_texto or tem_video or tem_laudo):
        raise HTTPException(
            status_code=400,
            detail="Envie ao menos uma modalidade: 'texto', 'video_arquivo' e/ou 'laudo_arquivo'.",
        )

    s = get_settings()

    # ----- modalidade texto -----
    categorias_texto = None
    nlp_result = None
    if tem_texto:
        categorias_texto, nlp_result = extrair_categorias_e_nlp(texto, nlp)

    # ----- modalidade video -----
    categorias_video = None
    video_result = None
    if tem_video:
        nome = video_arquivo.filename or "video.mp4"
        if _sufixo(nome) not in EXTENSOES_SUPORTADAS:
            raise HTTPException(
                status_code=415,
                detail=f"Formato de video nao suportado: {sorted(EXTENSOES_SUPORTADAS)}.",
            )
        conteudo = await video_arquivo.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail="Arquivo de video vazio.")
        video_result, categorias_video = analisar_video(
            nome_arquivo=nome,
            conteudo=conteudo,
            video=video,
            classes_foco=s.video_focus_classes_list,
            amostragem=s.video_frame_sample,
            conf=s.video_conf_threshold,
            storage=storage,
        )

    # ----- modalidade laudo -----
    categorias_laudo = None
    nlp_laudo = None
    texto_documento = resumo = backend_ocr = backend_sum = None
    if tem_laudo:
        nome = laudo_arquivo.filename or "laudo.pdf"
        if _sufixo(nome) not in EXT_LAUDO:
            raise HTTPException(status_code=415, detail="Laudo deve ser um PDF.")
        conteudo = await laudo_arquivo.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail="Arquivo de laudo vazio.")
        resultado = analisar_laudo(
            nome_arquivo=nome,
            conteudo=conteudo,
            ocr=ocr,
            nlp=nlp,
            summarizer=summarizer,
            storage=storage,
        )
        categorias_laudo = resultado.categorias
        nlp_laudo = resultado.nlp
        texto_documento = resultado.ocr.texto
        resumo = resultado.resumo
        backend_ocr = resultado.ocr.backend
        backend_sum = getattr(summarizer, "nome_backend", None) if resultado.resumo else None

    return fundir(
        categorias_texto=categorias_texto,
        nlp_result=nlp_result,
        categorias_video=categorias_video,
        video_result=video_result,
        categorias_laudo=categorias_laudo,
        nlp_laudo=nlp_laudo,
        texto_documento=texto_documento,
        resumo=resumo,
        backend_ocr=backend_ocr,
        backend_summarizer=backend_sum,
    )
