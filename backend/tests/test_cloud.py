"""
Testes dos adapters de NUVEM SEM tocar a AWS.

Construimos o adapter normalmente (boto3 cria o client, mas nao chama a AWS) e
substituimos o client por um FAKE. Assim testamos a logica de mapeamento/parsing
sem credenciais, sem rede e sem custo. O smoke real fica em scripts/smoke_aws.py.
"""

from __future__ import annotations

import io

import pytest

pytest.importorskip("boto3")

from backend.app.ports.nlp import ComprehendAdapter
from backend.app.ports.storage import S3StorageAdapter


# --------------------- Comprehend ---------------------
def test_comprehend_truncar_respeita_limite_bytes():
    # 'a' com acento ocupa 2 bytes em UTF-8; 5000 caracteres => 10000 bytes
    texto = "á" * 5000
    truncado = ComprehendAdapter._truncar(texto, limite_bytes=4900)
    assert len(truncado.encode("utf-8")) <= 4900


class _FakeComprehend:
    def detect_sentiment(self, Text, LanguageCode):
        return {
            "Sentiment": "NEGATIVE",
            "SentimentScore": {"Positive": 0.1, "Negative": 0.8, "Neutral": 0.1, "Mixed": 0.0},
        }

    def detect_entities(self, Text, LanguageCode):
        return {"Entities": [{"Text": "insonia", "Type": "OTHER"}]}


def test_comprehend_mapeia_resposta():
    adapter = ComprehendAdapter(region="us-east-1")
    adapter.client = _FakeComprehend()  # injeta o fake
    resultado = adapter.analisar("texto qualquer")
    assert resultado.sentimento.rotulo == "negativo"
    assert resultado.sentimento.score == round(0.1 - 0.8, 3)
    assert any(e.texto == "insonia" for e in resultado.entidades)


# --------------------- S3 ---------------------
class _FakeS3:
    def __init__(self):
        self.store: dict = {}

    def put_object(self, Bucket, Key, Body):
        self.store[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.store[(Bucket, Key)])}


def test_s3_salvar_e_ler():
    adapter = S3StorageAdapter(bucket="meu-bucket", region="us-east-1")
    adapter.client = _FakeS3()  # injeta o fake
    uri = adapter.salvar("pasta/arquivo.txt", b"conteudo")
    assert uri == "s3://meu-bucket/pasta/arquivo.txt"
    assert adapter.ler(uri) == b"conteudo"
