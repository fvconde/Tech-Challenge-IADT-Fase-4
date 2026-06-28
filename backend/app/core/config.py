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

    # ----- Caminhos / idioma -----
    local_storage_dir: str = "data/storage"
    transcription_language: str = "pt-BR"

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
