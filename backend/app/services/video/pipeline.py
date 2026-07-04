"""
Pipeline de analise de VIDEO/IMAGEM (agora MULTIMODAL).

Um unico arquivo de video/imagem pode ser analisado por varias tecnicas, todas
lendo do MESMO arquivo temporario:

    arquivo --[StoragePort opcional]--> salvo
            --[VideoPort:  YOLOv8]-----> objetos            -> risk_rules
            --[PosePort:   MediaPipe]--> sinais corporais   -> pose_rules
            --[EmotionPort:DeepFace]---> emocao facial      -> emotion_rules
            --[moviepy -> TranscriptionPort -> NLP]--------> fala (trilha de audio)

Cada tecnica e ISOLADA: a falha de uma (lib ausente, sem rosto, sem trilha) NAO
derruba as outras -- registra warning e segue. Pose/emocao com backend 'mock'
(default) sao tratadas como AUSENTES, para o comportamento padrao do endpoint
permanecer identico (so 'video'). O resultado bruto de cada tecnica volta junto
com as categorias de risco, para o router montar UM alerta na fusao.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.app.ports.base import (
    DeteccaoCategoria,
    EmotionAnalysisResult,
    EmotionPort,
    NlpPort,
    NlpResult,
    PoseAnalysisResult,
    PosePort,
    StoragePort,
    TranscriptionPort,
    VideoAnalysisResult,
    VideoPort,
)
from backend.app.services.audio.extract import extrair_audio_de_video
from backend.app.services.text.nlp import extrair_categorias_e_nlp
from backend.app.services.video.emotion_rules import avaliar_risco_emocao
from backend.app.services.video.pose_rules import avaliar_risco_pose
from backend.app.services.video.risk_rules import avaliar_risco_visual

logger = logging.getLogger(__name__)


@dataclass
class VideoPipelineResult:
    """
    Pecas BRUTAS de cada tecnica aplicada ao video (o router as entrega a fusao).

    Uma modalidade so esta "presente" (lista != None) quando ela realmente rodou:
    isso preserva o comportamento padrao (so 'video') quando pose/emocao/trilha
    estao desligadas (mock/flag off).
    """
    video_result: VideoAnalysisResult
    categorias_video: list[DeteccaoCategoria]
    pose_result: PoseAnalysisResult | None = None
    categorias_pose: list[DeteccaoCategoria] | None = None
    emotion_result: EmotionAnalysisResult | None = None
    categorias_emocao: list[DeteccaoCategoria] | None = None
    transcricao: str | None = None
    backend_transcricao: str | None = None
    nlp_result: NlpResult | None = None
    categorias_texto: list[DeteccaoCategoria] | None = None


def analisar_video(
    nome_arquivo: str,
    conteudo: bytes,
    video: VideoPort,
    classes_foco: list[str],
    amostragem: int = 15,
    conf: float = 0.25,
    storage: StoragePort | None = None,
    pose: PosePort | None = None,
    emotion: EmotionPort | None = None,
    transcription: TranscriptionPort | None = None,
    nlp: NlpPort | None = None,
    transcrever_audio: bool = False,
    idioma: str = "pt-BR",
) -> VideoPipelineResult:
    """
    Analisa um video/imagem com as tecnicas fornecidas e devolve as pecas brutas.

    - video (obrigatorio): YOLOv8, como antes.
    - pose/emotion (opcionais): so contribuem quando o adapter NAO e mock.
    - transcrever_audio: se True e houver transcription+nlp, extrai a trilha
      (moviepy), transcreve e roda o NLP -> categorias de texto.
    """
    # 1) (opcional) persistir o arquivo recebido
    if storage is not None:
        ref = storage.salvar(f"video/{nome_arquivo}", conteudo)
        logger.info("Video/imagem armazenado em: %s", ref)

    # 2) gravar UM arquivo temporario (todas as tecnicas leem dele)
    sufixo = Path(nome_arquivo).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
        tmp.write(conteudo)
        caminho_tmp = tmp.name

    try:
        # 3) YOLO (sempre) -> objetos -> categorias visuais
        resultado = video.analisar(
            caminho_tmp, classes_foco=classes_foco, amostragem=amostragem, conf=conf
        )
        categorias_video = avaliar_risco_visual(resultado.deteccoes, classes_foco)

        bundle = VideoPipelineResult(
            video_result=resultado, categorias_video=categorias_video
        )

        # 4) POSE (MediaPipe) -- so conta se o backend for real (nao mock)
        _rodar_pose(bundle, pose, caminho_tmp, amostragem)

        # 5) EMOCAO (DeepFace) -- idem
        _rodar_emocao(bundle, emotion, caminho_tmp, amostragem)

        # 6) TRILHA DE AUDIO (moviepy -> transcricao -> NLP)
        if transcrever_audio and transcription is not None and nlp is not None:
            _rodar_trilha_audio(bundle, caminho_tmp, transcription, nlp, idioma)
    finally:
        try:
            Path(caminho_tmp).unlink(missing_ok=True)
        except OSError:  # pragma: no cover
            pass

    return bundle


def _rodar_pose(
    bundle: VideoPipelineResult, pose: PosePort | None, caminho: str, amostragem: int
) -> None:
    """
    Roda a analise de pose e anexa ao bundle (isolada: falha nao propaga).

    So marca a modalidade 'pose' como presente quando HOUVE deteccao (sinais nao
    vazios). Assim o default (adapter mock retorna vazio) mantem o comportamento
    padrao do endpoint (so 'video'), sem depender do nome do backend.
    """
    if pose is None:
        return
    try:
        res = pose.analisar(caminho, amostragem=amostragem)
    except Exception:
        logger.warning("Analise de pose falhou (ignorada).", exc_info=True)
        return
    if not res.sinais:
        return  # nada detectado: modalidade ausente
    bundle.pose_result = res
    bundle.categorias_pose = avaliar_risco_pose(res.sinais)


def _rodar_emocao(
    bundle: VideoPipelineResult, emotion: EmotionPort | None, caminho: str, amostragem: int
) -> None:
    """
    Roda a analise de emocao e anexa ao bundle (isolada: falha nao propaga).

    Presente quando ha rostos analisados (emocoes nao vazias). As categorias podem
    ficar vazias se as emocoes forem so positivas (emocao vista, sem risco).
    """
    if emotion is None:
        return
    try:
        res = emotion.analisar(caminho, amostragem=amostragem)
    except Exception:
        logger.warning("Analise de emocao falhou (ignorada).", exc_info=True)
        return
    if not res.emocoes:
        return  # nenhum rosto/emocao: modalidade ausente
    bundle.emotion_result = res
    bundle.categorias_emocao = avaliar_risco_emocao(res.emocoes)


def _rodar_trilha_audio(
    bundle: VideoPipelineResult,
    caminho_video: str,
    transcription: TranscriptionPort,
    nlp: NlpPort,
    idioma: str,
) -> None:
    """Extrai a trilha, transcreve e roda o NLP (isolada: falha nao propaga)."""
    caminho_wav: str | None = None
    try:
        caminho_wav = extrair_audio_de_video(caminho_video)
        transcricao = transcription.transcrever(caminho_wav, idioma=idioma)
        bundle.transcricao = transcricao.texto
        bundle.backend_transcricao = transcricao.backend
        if transcricao.texto.strip():
            categorias, nlp_result = extrair_categorias_e_nlp(transcricao.texto, nlp)
            bundle.categorias_texto = categorias
            bundle.nlp_result = nlp_result
        else:
            # trilha vazia/nao compreendida: modalidade presente, sem categorias
            bundle.categorias_texto = []
    except Exception:
        logger.warning("Transcricao da trilha de audio falhou (ignorada).", exc_info=True)
    finally:
        if caminho_wav is not None:
            try:
                Path(caminho_wav).unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                pass
