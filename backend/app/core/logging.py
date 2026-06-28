"""Configuracao simples de logging para a aplicacao."""

from __future__ import annotations

import logging

from backend.app.core.config import get_settings


def configurar_logging() -> None:
    """Configura o logging raiz com base no LOG_LEVEL do .env."""
    settings = get_settings()
    nivel = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
