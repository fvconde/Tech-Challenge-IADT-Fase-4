"""
Fabrica de adapters (composition root).

Aqui e o UNICO lugar que decide qual implementacao concreta de cada porta sera
usada, com base nas variaveis de ambiente (Settings). O resto do sistema pede a
porta pela interface e recebe ja o adapter certo (local por padrao).

Isto e o equivalente ao registro de servicos da injecao de dependencia do .NET
(ex.: services.AddScoped<INlp, LocalNlp>()).

IMPORTANTE: estas funcoes sao usadas como dependencias do FastAPI (Depends).
Por isso NAO recebem parametros: o FastAPI inspeciona a assinatura de cada
dependencia e trataria um parametro tipado como Settings (modelo Pydantic) como
um campo do corpo da requisicao. Mantemos a assinatura limpa e lemos as
configuracoes internamente via get_settings().
"""

from __future__ import annotations

import logging

from backend.app.core.config import get_settings
from backend.app.ports.base import NlpPort, StoragePort, TranscriptionPort, VideoPort
from backend.app.ports.nlp import ComprehendAdapter, LocalNlpAdapter
from backend.app.ports.storage import LocalStorageAdapter, S3StorageAdapter
from backend.app.ports.transcription import (
    MockTranscriptionAdapter,
    RecognizeGoogleAdapter,
)
from backend.app.ports.video import LocalVideoAdapter, MockVideoAdapter

logger = logging.getLogger(__name__)


def get_storage() -> StoragePort:
    settings = get_settings()
    if settings.storage_backend == "s3":
        logger.info("StoragePort -> S3StorageAdapter (cloud)")
        return S3StorageAdapter(
            bucket=settings.s3_bucket_name, region=settings.aws_region
        )
    logger.info("StoragePort -> LocalStorageAdapter (local)")
    return LocalStorageAdapter(base_dir=settings.local_storage_dir)


def get_nlp() -> NlpPort:
    settings = get_settings()
    if settings.nlp_backend == "comprehend":
        logger.info("NlpPort -> ComprehendAdapter (cloud)")
        return ComprehendAdapter(region=settings.aws_region)
    logger.info("NlpPort -> LocalNlpAdapter (local)")
    return LocalNlpAdapter()


def get_transcription() -> TranscriptionPort:
    settings = get_settings()
    if settings.transcription_backend == "mock":
        logger.info("TranscriptionPort -> MockTranscriptionAdapter (offline)")
        return MockTranscriptionAdapter()
    logger.info("TranscriptionPort -> RecognizeGoogleAdapter (Google Web Speech)")
    return RecognizeGoogleAdapter()


def get_video() -> VideoPort:
    settings = get_settings()
    if settings.video_backend == "mock":
        logger.info("VideoPort -> MockVideoAdapter (offline)")
        return MockVideoAdapter()
    logger.info("VideoPort -> LocalVideoAdapter (YOLOv8 %s)", settings.video_model)
    return LocalVideoAdapter(modelo=settings.video_model)
