"""
Endpoint de FUSAO MULTIMODAL.

Recebe texto (e/ou) video e devolve UM unico alerta combinando as modalidades.
Demonstra o coracao do desafio: fundir sinais de diferentes tipos de dado.

Como aceita upload de arquivo + campo de texto, usa multipart/form-data
(parametros Form/File), e nao JSON.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import NlpPort, StoragePort, VideoPort
from backend.app.ports.factory import get_nlp, get_storage, get_video
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.text.nlp import extrair_categorias_e_nlp
from backend.app.services.video.pipeline import analisar_video
from backend.app.api.routers.video import EXTENSOES_SUPORTADAS, _sufixo

router = APIRouter(prefix="/api/fusion", tags=["fusao"])


@router.post("/analyze", response_model=AnaliseRiscoResponse)
async def analisar(
    texto: str | None = Form(
        default=None, description="Relato/transcricao (opcional)"
    ),
    video_arquivo: UploadFile | None = File(
        default=None, description="Video ou imagem clinica (opcional)"
    ),
    nlp: NlpPort = Depends(get_nlp),
    video: VideoPort = Depends(get_video),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Funde texto + video em um alerta unico.

    Pelo menos UMA das modalidades deve ser enviada. Se as duas chegarem e
    apontarem o mesmo risco, a fusao aplica boost de corroboracao (ver
    services/fusion/alerts.py).
    """
    tem_texto = bool(texto and texto.strip())
    tem_video = video_arquivo is not None and bool(video_arquivo.filename)
    if not tem_texto and not tem_video:
        raise HTTPException(
            status_code=400,
            detail="Envie ao menos uma modalidade: 'texto' e/ou 'video_arquivo'.",
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

    return fundir(
        categorias_texto=categorias_texto,
        nlp_result=nlp_result,
        categorias_video=categorias_video,
        video_result=video_result,
    )
