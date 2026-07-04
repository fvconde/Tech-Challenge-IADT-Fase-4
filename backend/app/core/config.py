"""
Configuracao central da aplicacao.

Lemos as variaveis de ambiente (e o arquivo .env, se existir) com pydantic-settings.
TODOS os defaults apontam para a implementacao LOCAL, para que o sistema suba sem
nenhuma credencial de nuvem (requisito nao-negociavel do projeto).

Uso:
    from backend.app.core.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Le o .env automaticamente; ignora variaveis extras que nao mapeamos aqui.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ----- Selecao de backend (local default | cloud opcional) -----
    storage_backend: str = "local"                  # local | s3
    nlp_backend: str = "local"                      # local | comprehend
    transcription_backend: str = "recognize_google" # recognize_google | mock
    video_backend: str = "local"                    # local | mock
    # Pose (MediaPipe) e emocao (DeepFace) sao ADITIVAS e puxam libs pesadas, entao
    # o default e 'mock' (retorna vazio): o app sobe e /api/video funciona igual sem
    # elas instaladas. Ative na demo com POSE_BACKEND=local / EMOTION_BACKEND=local.
    pose_backend: str = "mock"                      # local | mock
    emotion_backend: str = "mock"                   # local | mock
    ocr_backend: str = "local"                      # local | mock (sem Textract!)
    summarizer_backend: str = "distilbart"          # distilbart | extractive

    # ----- Caminhos / idioma -----
    local_storage_dir: str = "data/storage"
    transcription_language: str = "pt-BR"

    # ----- Video (YOLOv8) -----
    video_model: str = "yolov8n.pt"                 # modelo pre-treinado (custo zero)
    # Classes COCO monitoradas como proxy de "objeto suspeito de automutilacao".
    # Configuravel: separe por virgula no .env (ex.: "knife,scissors").
    video_focus_classes: str = "knife,scissors"
    video_frame_sample: int = 15                    # analisa 1 frame a cada N
    video_conf_threshold: float = 0.25              # confianca minima da deteccao
    # Transcrever a TRILHA DE AUDIO do video (moviepy -> TranscriptionPort -> NLP).
    # Default False: com transcription_backend=recognize_google isso ENVIA o audio
    # ao Google (LGPD). Ative conscientemente na demo com VIDEO_TRANSCREVER_AUDIO=true.
    video_transcrever_audio: bool = False

    @property
    def video_focus_classes_list(self) -> list[str]:
        """Converte a string 'knife,scissors' em ['knife', 'scissors']."""
        return [c.strip() for c in self.video_focus_classes.split(",") if c.strip()]

    # ----- Pose (MediaPipe Tasks) -----
    # Modelo .task do PoseLandmarker; baixado 1x do Google se ausente (como o YOLO).
    # Aponte para um arquivo local para rodar offline.
    pose_model: str = "pose_landmarker_lite.task"

    # ----- Sumarizacao -----
    # Modelo HF para o backend distilbart (treinado em ingles; ver relatorio).
    summarizer_model: str = "sshleifer/distilbart-cnn-12-6"

    # ----- AWS (opcional; vazio = nao usar nuvem) -----
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket_name: str = ""

    # ----- App -----
    app_env: str = "dev"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Devolve uma instancia unica de Settings (cacheada)."""
    return Settings()
