"""
Adapters de NLP (NlpPort): sentimento + extracao de entidades.

- LocalNlpAdapter: 100% local, sem nuvem. Usa um lexico de sentimento em PT-BR
  (abordagem simples e EXPLICAVEL, boa para apoio a decisao) e regex para extrair
  entidades basicas (sintomas, medicamentos, marcadores de tempo). Default.
- ComprehendAdapter: usa Amazon Comprehend. OPCIONAL (consome credito) e so e
  acionado na demo final via NLP_BACKEND=comprehend. Import lazy do boto3.

Por que lexico em vez de um modelo grande? Transparencia e custo zero: cada
decisao e rastreavel ate as palavras que a motivaram (ver "evidencias"). Um
classificador supervisionado (sklearn) complementa isso na camada de servico
(services/text/classifier.py).
"""

from __future__ import annotations

import logging
import re
import unicodedata

from backend.app.ports.base import (
    Entidade,
    NlpPort,
    NlpResult,
    SentimentResult,
)

logger = logging.getLogger(__name__)


# --- Lexicos de sentimento (PT-BR), em minusculas e SEM acento (normalizamos) ---
PALAVRAS_NEGATIVAS = {
    "triste", "tristeza", "choro", "chorar", "chorando", "medo", "assustada",
    "ansiosa", "ansiedade", "angustia", "angustiada", "sozinha", "cansada",
    "exausta", "fadiga", "dor", "dores", "sofrimento", "fracasso", "culpa",
    "desespero", "panico", "insonia", "vazia", "inutil", "machucada", "apanhei",
    "bati", "empurrou", "gritou", "ameaca", "ameacou", "controla", "vergonha",
    "nervosa", "preocupada", "horrivel", "pior", "nao", "nunca", "ninguem",
}
PALAVRAS_POSITIVAS = {
    "bem", "feliz", "felicidade", "tranquila", "calma", "esperanca", "melhor",
    "otima", "otimo", "aliviada", "alivio", "apoiada", "segura", "confiante",
    "animada", "grata", "obrigada", "amor", "saudavel", "recuperada", "boa",
}

# --- Padroes simples para entidades ---
PADRAO_TEMPO = re.compile(
    r"\b(\d+\s*(dia|dias|semana|semanas|mes|meses|ano|anos|hora|horas))\b"
)
SINTOMAS_CONHECIDOS = {
    "insonia", "enjoo", "nausea", "tontura", "sangramento", "dor de cabeca",
    "falta de ar", "palpitacao", "inchaco", "febre", "calafrio", "cansaco",
    "choro", "ansiedade", "tristeza",
}
MEDICAMENTOS_CONHECIDOS = {
    "anticoncepcional", "hormonio", "progesterona", "estrogeno", "insulina",
    "antidepressivo", "sertralina", "fluoxetina", "acido folico", "ocitocina",
}


def _normalizar(texto: str) -> str:
    """Minuscula + remove acentos, para casar com os lexicos."""
    texto = texto.lower()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokenizar(texto_normalizado: str) -> list[str]:
    return re.findall(r"[a-z]+", texto_normalizado)


class LocalNlpAdapter(NlpPort):
    """Analise local por lexico + regex. Sem rede, sem custo."""

    def analisar(self, texto: str) -> NlpResult:
        norm = _normalizar(texto)
        tokens = _tokenizar(norm)

        neg = sum(1 for t in tokens if t in PALAVRAS_NEGATIVAS)
        pos = sum(1 for t in tokens if t in PALAVRAS_POSITIVAS)

        total = neg + pos
        if total == 0:
            score = 0.0
            rotulo = "neutro"
        else:
            # score em [-1, 1]: (pos - neg) / (pos + neg)
            score = round((pos - neg) / total, 3)
            if score > 0.2:
                rotulo = "positivo"
            elif score < -0.2:
                rotulo = "negativo"
            else:
                rotulo = "neutro"

        entidades = self._extrair_entidades(texto, norm)
        return NlpResult(
            sentimento=SentimentResult(rotulo=rotulo, score=score, backend="local"),
            entidades=entidades,
        )

    def _extrair_entidades(self, texto_original: str, norm: str) -> list[Entidade]:
        entidades: list[Entidade] = []

        for sintoma in SINTOMAS_CONHECIDOS:
            if _normalizar(sintoma) in norm:
                entidades.append(Entidade(texto=sintoma, tipo="sintoma"))

        for med in MEDICAMENTOS_CONHECIDOS:
            if _normalizar(med) in norm:
                entidades.append(Entidade(texto=med, tipo="medicamento"))

        for match in PADRAO_TEMPO.finditer(norm):
            entidades.append(Entidade(texto=match.group(1), tipo="tempo"))

        return entidades


class ComprehendAdapter(NlpPort):
    """
    NLP via Amazon Comprehend. OPCIONAL e consome credito AWS.

    So deve ser usado na demo final (NLP_BACKEND=comprehend). Import lazy do boto3.
    """

    def __init__(self, region: str = "us-east-1", language: str = "pt") -> None:
        try:
            import boto3  # lazy
        except ImportError as exc:  # pragma: no cover - cloud opcional
            raise RuntimeError(
                "ComprehendAdapter requer boto3. Use NLP_BACKEND=local para rodar offline."
            ) from exc
        self.client = boto3.client("comprehend", region_name=region)
        self.language = language

    def analisar(self, texto: str) -> NlpResult:  # pragma: no cover - cloud
        sent = self.client.detect_sentiment(Text=texto, LanguageCode=self.language)
        # Comprehend devolve POSITIVE/NEGATIVE/NEUTRAL/MIXED + scores
        mapa = {"POSITIVE": "positivo", "NEGATIVE": "negativo",
                "NEUTRAL": "neutro", "MIXED": "neutro"}
        rotulo = mapa.get(sent["Sentiment"], "neutro")
        s = sent["SentimentScore"]
        score = round(s.get("Positive", 0) - s.get("Negative", 0), 3)

        ents_resp = self.client.detect_entities(Text=texto, LanguageCode=self.language)
        entidades = [
            Entidade(texto=e["Text"], tipo=e["Type"].lower())
            for e in ents_resp.get("Entities", [])
        ]
        return NlpResult(
            sentimento=SentimentResult(rotulo=rotulo, score=score, backend="comprehend"),
            entidades=entidades,
        )
