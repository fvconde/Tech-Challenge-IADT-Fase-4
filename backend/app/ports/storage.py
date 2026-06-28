"""
Adapters de armazenamento (StoragePort).

- LocalStorageAdapter: grava no filesystem. Default, custo zero, sem nuvem.
- S3StorageAdapter: grava em bucket S3 (Always-Free). OPCIONAL: so e usado se
  STORAGE_BACKEND=s3 e credenciais estiverem presentes. O import do boto3 e
  preguicoso (lazy) de proposito, para que o sistema suba sem boto3 instalado.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.ports.base import StoragePort

logger = logging.getLogger(__name__)


class LocalStorageAdapter(StoragePort):
    """Armazena arquivos no disco local, dentro de um diretorio base."""

    def __init__(self, base_dir: str = "data/storage") -> None:
        self.base_dir = Path(base_dir)
        # cria o diretorio na inicializacao (idempotente)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def salvar(self, nome: str, conteudo: bytes) -> str:
        destino = self.base_dir / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        logger.info("Arquivo salvo localmente: %s (%d bytes)", destino, len(conteudo))
        return str(destino)

    def ler(self, referencia: str) -> bytes:
        return Path(referencia).read_bytes()


class S3StorageAdapter(StoragePort):
    """
    Armazena arquivos em um bucket S3.

    OPCIONAL. O boto3 so e importado quando este adapter e realmente instanciado,
    para nao obrigar o sistema a ter boto3/credenciais para subir.
    """

    def __init__(self, bucket: str, region: str = "us-east-1") -> None:
        try:
            import boto3  # import lazy: so quando o adapter cloud e escolhido
        except ImportError as exc:  # pragma: no cover - caminho de nuvem opcional
            raise RuntimeError(
                "S3StorageAdapter requer boto3. Instale com 'pip install boto3' "
                "ou use STORAGE_BACKEND=local."
            ) from exc

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region)

    def salvar(self, nome: str, conteudo: bytes) -> str:  # pragma: no cover - cloud
        self.client.put_object(Bucket=self.bucket, Key=nome, Body=conteudo)
        uri = f"s3://{self.bucket}/{nome}"
        logger.info("Arquivo salvo no S3: %s", uri)
        return uri

    def ler(self, referencia: str) -> bytes:  # pragma: no cover - cloud
        # referencia no formato s3://bucket/key
        _, _, resto = referencia.partition("s3://")
        bucket, _, key = resto.partition("/")
        obj = self.client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
