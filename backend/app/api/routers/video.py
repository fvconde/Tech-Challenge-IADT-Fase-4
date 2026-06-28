"""Endpoints de analise de VIDEO/IMAGEM (YOLOv8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import StoragePort, VideoPort
from backend.app.ports.factory import get_storage, get_video
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.video.pipeline import analisar_video

router = APIRouter(prefix="/api/video", tags=["video"])

# Formatos aceitos (imagem ou video).
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
EXTENSOES_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
EXTENSOES_SUPORTADAS = EXTENSOES_IMAGEM | EXTENSOES_VIDEO


def _sufixo(nome: str) -> str:
    return "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""


@router.get("/status")
def status() -> dict:
    """Estado do modulo de video e configuracao ativa."""
    s = get_settings()
    return {
        "modulo": "video",
        "backend": s.video_backend,
        "modelo": s.video_model,
        "classes_foco": s.video_focus_classes_list,
        "amostragem_frames": s.video_frame_sample,
    }


@router.post("/analyze", response_model=AnaliseRiscoResponse)
async def analisar(
    arquivo: UploadFile = File(..., description="Imagem ou video clinico de exemplo"),
    video: VideoPort = Depends(get_video),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Detecta objetos no video/imagem (YOLOv8) e converte em risco visual.

    A deteccao usa classes COCO genericas; as REGRAS DE RISCO (classes-foco
    configuraveis, ex.: knife/scissors) decidem o que vira alerta. Sem treino
    customizado e 100% local.
    """
    nome = arquivo.filename or "video.mp4"
    if _sufixo(nome) not in EXTENSOES_SUPORTADAS:
        raise HTTPException(
            status_code=415,
            detail=f"Formato nao suportado. Envie um de: {sorted(EXTENSOES_SUPORTADAS)}.",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    s = get_settings()
    resultado, categorias_video = analisar_video(
        nome_arquivo=nome,
        conteudo=conteudo,
        video=video,
        classes_foco=s.video_focus_classes_list,
        amostragem=s.video_frame_sample,
        conf=s.video_conf_threshold,
        storage=storage,
    )

    # resposta unificada (modalidade unica: video)
    return fundir(categorias_video=categorias_video, video_result=resultado)
