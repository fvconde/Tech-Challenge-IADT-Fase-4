"""
Endpoint de FUSAO MULTIMODAL.

Recebe texto, audio, video, imagem e/ou laudo (PDF) e devolve UM unico alerta
combinando TODAS as modalidades enviadas. Demonstra o coracao do desafio: fundir
sinais de diferentes tipos de dado.

- audio (WAV/FLAC): transcrito -> NLP -> modalidade 'audio'.
- video E imagem: ambos passam pelo YOLO (+pose/emocao no video); as deteccoes e
  categorias visuais sao COMBINADAS -> a imagem NAO e descartada quando ha video.
- texto e laudo: como antes.

Como aceita uploads + campo de texto, usa multipart/form-data (Form/File), nao JSON.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.app.api.routers.audio import EXTENSOES_SUPORTADAS as EXT_AUDIO
from backend.app.api.routers.laudo import EXTENSOES_SUPORTADAS as EXT_LAUDO
from backend.app.api.routers.video import EXTENSOES_SUPORTADAS as EXT_VISUAL
from backend.app.api.routers.video import _sufixo
from backend.app.core.config import get_settings
from backend.app.models.schemas import AnaliseRiscoResponse
from backend.app.ports.base import (
    EmotionAnalysisResult,
    EmotionPort,
    NlpPort,
    NlpResult,
    OcrPort,
    PoseAnalysisResult,
    PosePort,
    StoragePort,
    SummarizerPort,
    TranscriptionPort,
    VideoAnalysisResult,
    VideoPort,
)
from backend.app.ports.factory import (
    get_emotion,
    get_nlp,
    get_ocr,
    get_pose,
    get_storage,
    get_summarizer,
    get_transcription,
    get_video,
)
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.text.document import analisar_laudo
from backend.app.services.text.nlp import extrair_categorias_e_nlp
from backend.app.services.video.pipeline import analisar_video

router = APIRouter(prefix="/api/fusion", tags=["fusao"])
logger = logging.getLogger(__name__)


def _extrair_audio_categorias(nome, conteudo, transcription, nlp, storage, idioma):
    """Transcreve um audio e devolve (categorias, nlp_result, texto, backend_transcricao).

    Mesmo padrao do /api/audio: grava um temporario (a transcricao exige um path),
    transcreve e reusa o pipeline de texto (extrair_categorias_e_nlp).

    ISOLADO: se a transcricao falhar (ex.: arquivo nao e um WAV/FLAC valido), NAO
    derruba a fusao -- registra warning e devolve tudo None (modalidade audio ausente).
    """
    if storage is not None:
        storage.salvar(f"audio/{nome}", conteudo)
    sufixo = Path(nome).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
        tmp.write(conteudo)
        caminho = tmp.name
    tr = None
    try:
        tr = transcription.transcrever(caminho, idioma=idioma)
    except Exception:
        logger.warning("Transcricao do audio na fusao falhou (ignorada).", exc_info=True)
    finally:
        try:
            Path(caminho).unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass
    if tr is None:
        return None, None, None, None
    if tr.texto.strip():
        categorias, nlp_res = extrair_categorias_e_nlp(tr.texto, nlp)
    else:
        categorias, nlp_res = [], None
    return categorias, nlp_res, tr.texto, tr.backend


def _combinar_nlp(*results: NlpResult | None) -> NlpResult | None:
    """Une NlpResults de texto/audio: sentimento MAIS NEGATIVO + uniao de entidades."""
    presentes = [r for r in results if r is not None]
    if not presentes:
        return None
    sentimento = min((r.sentimento for r in presentes), key=lambda s: s.score)
    entidades = [e for r in presentes for e in r.entidades]
    return NlpResult(sentimento=sentimento, entidades=entidades)


def _merge_visuais(bundles: list):
    """Combina 1+ bundles de video/imagem num unico conjunto de pecas para a fusao.

    A imagem NAO e descartada: deteccoes e categorias visuais dos dois arquivos sao
    UNIDAS (uma unica modalidade 'video'). Pose/emocao vem de onde houver (o video,
    tipicamente). A imagem anotada exibida prioriza a que tem categoria de foco
    (ex.: tesoura -> objeto_suspeito), senao a primeira anotacao disponivel.
    """
    if not bundles:
        return None, None, None, None, None, None, None

    deteccoes = []
    frames = 0
    backend = "local"
    anotada_foco = None       # anotacao de um visual QUE gerou categoria de risco
    anotada_qualquer = None   # fallback: qualquer anotacao disponivel
    cats_video: list = []
    for b in bundles:
        vr = b.video_result
        deteccoes.extend(vr.deteccoes)
        frames += vr.frames_analisados
        backend = vr.backend or backend
        if b.categorias_video:
            cats_video.extend(b.categorias_video)
            if anotada_foco is None:
                anotada_foco = vr.imagem_anotada_b64
        if anotada_qualquer is None and vr.imagem_anotada_b64:
            anotada_qualquer = vr.imagem_anotada_b64
    video_result = VideoAnalysisResult(
        deteccoes=deteccoes,
        frames_analisados=frames,
        backend=backend,
        imagem_anotada_b64=anotada_foco or anotada_qualquer,
    )

    # POSE: une sinais e categorias de onde houver (modalidade presente se algum rodou)
    sinais = []
    cats_pose = None
    pose_backend = "local"
    for b in bundles:
        if b.categorias_pose is not None:
            cats_pose = (cats_pose or []) + b.categorias_pose
        if b.pose_result is not None:
            sinais.extend(b.pose_result.sinais)
            pose_backend = b.pose_result.backend
    pose_result = PoseAnalysisResult(sinais=sinais, backend=pose_backend) if sinais else None

    # EMOCAO: idem
    emocoes = []
    cats_emo = None
    emo_backend = "local"
    for b in bundles:
        if b.categorias_emocao is not None:
            cats_emo = (cats_emo or []) + b.categorias_emocao
        if b.emotion_result is not None:
            emocoes.extend(b.emotion_result.emocoes)
            emo_backend = b.emotion_result.backend
    emotion_result = (
        EmotionAnalysisResult(emocoes=emocoes, backend=emo_backend) if emocoes else None
    )

    # PAINEL de emocao (hexagono + video anotado): pega o primeiro disponivel
    # (tipicamente so o video gera painel; imagem nao passa por anotacao).
    emocao_panel = next((b.emocao_panel for b in bundles if b.emocao_panel), None)

    return (
        cats_video,
        video_result,
        cats_pose,
        pose_result,
        cats_emo,
        emotion_result,
        emocao_panel,
    )


@router.post(
    "/analyze",
    response_model=AnaliseRiscoResponse,
    summary="Análise multimodal (fusão)",
)
async def analisar(
    texto: str | None = Form(default=None, description="Relato/transcricao (opcional)"),
    audio_arquivo: UploadFile | None = File(
        default=None, description="Audio da consulta - WAV/FLAC (opcional)"
    ),
    video_arquivo: UploadFile | None = File(
        default=None, description="Video ou imagem clinica (opcional)"
    ),
    imagem_arquivo: UploadFile | None = File(
        default=None, description="Imagem clinica adicional (opcional; combinada com o video)"
    ),
    laudo_arquivo: UploadFile | None = File(
        default=None, description="PDF de laudo (opcional)"
    ),
    nlp: NlpPort = Depends(get_nlp),
    video: VideoPort = Depends(get_video),
    pose: PosePort = Depends(get_pose),
    emotion: EmotionPort = Depends(get_emotion),
    transcription: TranscriptionPort = Depends(get_transcription),
    ocr: OcrPort = Depends(get_ocr),
    summarizer: SummarizerPort = Depends(get_summarizer),
    storage: StoragePort = Depends(get_storage),
) -> AnaliseRiscoResponse:
    """
    Funde texto + audio + video + imagem + laudo em um alerta unico.

    Pelo menos UMA das modalidades deve ser enviada. Video e imagem sao ambos
    analisados e COMBINADOS (a imagem nao e descartada). Quando duas ou mais
    modalidades apontam o mesmo risco, a fusao aplica boost de corroboracao.
    """
    tem_texto = bool(texto and texto.strip())
    tem_audio = audio_arquivo is not None and bool(audio_arquivo.filename)
    tem_video = video_arquivo is not None and bool(video_arquivo.filename)
    tem_imagem = imagem_arquivo is not None and bool(imagem_arquivo.filename)
    tem_laudo = laudo_arquivo is not None and bool(laudo_arquivo.filename)
    if not (tem_texto or tem_audio or tem_video or tem_imagem or tem_laudo):
        raise HTTPException(
            status_code=400,
            detail="Envie ao menos uma modalidade: 'texto', 'audio_arquivo', "
            "'video_arquivo', 'imagem_arquivo' e/ou 'laudo_arquivo'.",
        )

    s = get_settings()

    # ----- modalidade texto -----
    categorias_texto = nlp_texto = None
    if tem_texto:
        categorias_texto, nlp_texto = extrair_categorias_e_nlp(texto, nlp)

    # ----- modalidade audio (transcricao -> NLP) -----
    categorias_audio = nlp_audio = None
    transcricao = backend_transcricao = None
    if tem_audio:
        nome = audio_arquivo.filename or "audio.wav"
        if _sufixo(nome) not in EXT_AUDIO:
            raise HTTPException(
                status_code=415,
                detail=f"Formato de audio nao suportado: {sorted(EXT_AUDIO)}.",
            )
        conteudo = await audio_arquivo.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail="Arquivo de audio vazio.")
        categorias_audio, nlp_audio, transcricao, backend_transcricao = (
            _extrair_audio_categorias(
                nome, conteudo, transcription, nlp, storage, s.transcription_language
            )
        )

    # ----- modalidade visual (video E/OU imagem, combinados) -----
    bundles = []
    for arq in (video_arquivo, imagem_arquivo):
        if arq is None or not arq.filename:
            continue
        nome = arq.filename
        if _sufixo(nome) not in EXT_VISUAL:
            raise HTTPException(
                status_code=415,
                detail=f"Formato visual nao suportado ({nome}): {sorted(EXT_VISUAL)}.",
            )
        conteudo = await arq.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail=f"Arquivo visual vazio: {nome}.")
        bundles.append(
            analisar_video(
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
        )
    (
        categorias_video,
        video_result,
        categorias_pose,
        pose_result,
        categorias_emocao,
        emotion_result,
        emocao_panel,
    ) = _merge_visuais(bundles)

    # trilha de audio do(s) proprio(s) visual(is) -> modalidade "audio" (paridade
    # com /api/video/analyze: sem isso, um risco so audivel no video some na fusao).
    for b in bundles:
        if b.categorias_texto is None:
            continue  # imagem, sem fala, ou falha isolada (trilha ausente)
        categorias_audio = (categorias_audio or []) + b.categorias_texto
        nlp_audio = _combinar_nlp(nlp_audio, b.nlp_result)
        if transcricao is None and b.transcricao:  # prioriza o audio_arquivo dedicado
            transcricao = b.transcricao
            backend_transcricao = b.backend_transcricao

    # ----- modalidade laudo -----
    categorias_laudo = nlp_laudo = None
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
        nlp_result=_combinar_nlp(nlp_texto, nlp_audio),
        categorias_audio=categorias_audio,
        categorias_video=categorias_video,
        video_result=video_result,
        categorias_pose=categorias_pose,
        pose_result=pose_result,
        categorias_emocao=categorias_emocao,
        emotion_result=emotion_result,
        emocao_panel=emocao_panel,
        categorias_laudo=categorias_laudo,
        nlp_laudo=nlp_laudo,
        transcricao=transcricao,
        backend_transcricao=backend_transcricao,
        texto_documento=texto_documento,
        resumo=resumo,
        backend_ocr=backend_ocr,
        backend_summarizer=backend_sum,
    )
