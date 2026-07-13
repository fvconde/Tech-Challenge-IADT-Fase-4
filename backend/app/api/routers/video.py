"""Endpoint UNICO de analise de VIDEO/IMAGEM (YOLOv8 + pose + emocao + trilha de audio)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse

from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import (
    EmotionPort,
    NlpPort,
    PosePort,
    StoragePort,
    TranscriptionPort,
    VideoPort,
)
from backend.app.ports.factory import (
    get_emotion,
    get_nlp,
    get_pose,
    get_storage,
    get_transcription,
    get_video,
)
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.video import anotados
from backend.app.services.video.pipeline import analisar_video

router = APIRouter(prefix="/api/video", tags=["video"])

# Formatos aceitos (imagem ou video).
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
EXTENSOES_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
EXTENSOES_SUPORTADAS = EXTENSOES_IMAGEM | EXTENSOES_VIDEO


def _sufixo(nome: str) -> str:
    return "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""


@router.get("/status", summary="Status do módulo de vídeo")
def status() -> dict:
    """Estado do modulo de video (multimodal) e configuracao ativa."""
    s = get_settings()
    return {
        "modulo": "video",
        "backend": s.video_backend,
        "modelo": s.video_model,
        "classes_foco": s.video_focus_classes_list,
        "amostragem_frames": s.video_frame_sample,
        # tecnicas adicionais do video (default mock/off = nao interferem)
        "pose_backend": s.pose_backend,
        "emocao_backend": s.emotion_backend,
        "transcrever_audio": s.video_transcrever_audio,
    }


@router.post(
    "/analyze",
    response_model=AnaliseRiscoResponse,
    summary="Analisar vídeo/imagem (YOLOv8 + pose + emoção + trilha de áudio)",
)
async def analisar(
    arquivo: UploadFile = File(..., description="Imagem ou video clinico de exemplo"),
    video: VideoPort = Depends(get_video),
    pose: PosePort = Depends(get_pose),
    emotion: EmotionPort = Depends(get_emotion),
    transcription: TranscriptionPort = Depends(get_transcription),
    nlp: NlpPort = Depends(get_nlp),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Analise MULTIMODAL de um video/imagem, convergindo num unico alerta:
      - YOLOv8 (objetos, classes-foco configuraveis) -> risco visual;
      - MediaPipe (pose/gestos) quando POSE_BACKEND=local;
      - DeepFace (emocao facial) quando EMOTION_BACKEND=local -- para VIDEO, numa
        UNICA passada, tambem gera o video anotado + hexagono (``emocao_video``
        na resposta) e o serve via GET /api/video/anotado/{id};
      - trilha de audio (moviepy -> transcricao -> NLP) quando VIDEO_TRANSCREVER_AUDIO=true.

    Tudo 100% local e opt-in: por padrao (mocks/flag off) o comportamento e o mesmo
    de antes (so YOLO). Nenhum diagnostico: gera alerta para a equipe.
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
    bundle = analisar_video(
        nome_arquivo=nome,
        conteudo=conteudo,
        video=video,
        classes_foco=s.video_focus_classes_list,
        amostragem=s.video_frame_sample,
        conf=s.video_conf_threshold,
        storage=storage,
        pose=pose,
        emotion=emotion,
        transcription=transcription,
        nlp=nlp,
        transcrever_audio=s.video_transcrever_audio,
        idioma=s.transcription_language,
    )

    # resposta unificada (video + pose/emocao/painel/trilha quando ativos)
    return fundir(
        categorias_video=bundle.categorias_video,
        video_result=bundle.video_result,
        categorias_pose=bundle.categorias_pose,
        pose_result=bundle.pose_result,
        categorias_emocao=bundle.categorias_emocao,
        emotion_result=bundle.emotion_result,
        emocao_panel=bundle.emocao_panel,
        categorias_audio=bundle.categorias_texto,
        nlp_result=bundle.nlp_result,
        transcricao=bundle.transcricao,
        backend_transcricao=bundle.backend_transcricao,
    )


@router.get(
    "/anotado/{video_id}",
    summary="Baixar/reproduzir o vídeo anotado com emoções (MP4/H.264)",
)
def baixar_anotado(video_id: str) -> FileResponse:
    """Streaming do vídeo anotado gerado por POST /api/video/analyze (emocao_video)."""
    caminho = anotados.caminho_de(video_id)
    if caminho is None:
        raise HTTPException(
            status_code=404,
            detail="Vídeo anotado não encontrado (pode ter expirado ou o servidor reiniciou).",
        )
    return FileResponse(
        str(caminho), media_type="video/mp4", filename=f"anotado_{video_id}.mp4"
    )
