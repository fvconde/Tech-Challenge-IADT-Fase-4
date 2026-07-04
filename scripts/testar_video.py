"""Roda um video pelo pipeline multimodal de VISAO e imprime o alerta montado.

Espelha o `/api/video/analyze` usando os backends do `.env` (via a fabrica de adapters):
YOLO (sempre) + pose (MediaPipe) + emocao (DeepFace) conforme POSE_BACKEND/EMOTION_BACKEND.
NAO toca em storage (nao sobe nada). Com `--audio`, liga a trilha de audio
(MoviePy -> transcricao -> NLP), como VIDEO_TRANSCREVER_AUDIO=true.

Uso:
    python scripts/testar_video.py data/samples/paciente_demoV2.mp4
    python scripts/testar_video.py data/samples/paciente_demoV2_audio.mp4 --audio

Obs.: pose/emocao exigem POSE_BACKEND=local / EMOTION_BACKEND=local no .env (e as libs
mediapipe/deepface). Com --audio e TRANSCRIPTION_BACKEND=recognize_google, o audio vai
ao Google (usar so material sintetico).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como "python scripts/testar_video.py" (poe a raiz do projeto no sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.config import get_settings
from backend.app.ports.factory import (
    get_emotion,
    get_nlp,
    get_pose,
    get_transcription,
    get_video,
)
from backend.app.services.fusion.multimodal import fundir
from backend.app.services.video.pipeline import analisar_video


def testar(caminho: str, com_audio: bool) -> None:
    s = get_settings()
    video_path = Path(caminho)
    if not video_path.exists():
        sys.exit(f"Arquivo nao encontrado: {video_path}")
    conteudo = video_path.read_bytes()

    bundle = analisar_video(
        nome_arquivo=video_path.name,
        conteudo=conteudo,
        video=get_video(),
        classes_foco=s.video_focus_classes_list,
        amostragem=s.video_frame_sample,
        conf=s.video_conf_threshold,
        storage=None,  # nao sobe nada (o endpoint real pode persistir via StoragePort)
        pose=get_pose(),
        emotion=get_emotion(),
        transcription=get_transcription() if com_audio else None,
        nlp=get_nlp() if com_audio else None,
        transcrever_audio=com_audio,
        idioma=s.transcription_language,
    )

    resp = fundir(
        categorias_video=bundle.categorias_video,
        video_result=bundle.video_result,
        categorias_pose=bundle.categorias_pose,
        pose_result=bundle.pose_result,
        categorias_emocao=bundle.categorias_emocao,
        emotion_result=bundle.emotion_result,
        categorias_audio=bundle.categorias_texto,   # fala transcrita = modalidade 'audio'
        nlp_result=bundle.nlp_result,
        transcricao=bundle.transcricao,
        backend_transcricao=bundle.backend_transcricao,
    )

    print(f"\nArquivo    : {video_path}")
    if com_audio:
        print(f"Transcricao: {bundle.transcricao!r} (backend={bundle.backend_transcricao})")
    print(f"Nivel      : {resp.nivel_alerta}")
    print(f"Modalidades: {resp.modalidades}")
    for c in resp.categorias_risco:
        print(f"  - {c.categoria} (score {c.score})  {c.evidencias[:4]}")
    print(f"Acao       : {resp.acao_recomendada}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Testa um video pelo pipeline multimodal")
    parser.add_argument("video", nargs="?", default="data/samples/paciente_demoV2_audio.mp4")
    parser.add_argument("--audio", action="store_true",
                        help="liga a trilha de audio (transcricao + NLP)")
    args = parser.parse_args()
    testar(args.video, args.audio)
