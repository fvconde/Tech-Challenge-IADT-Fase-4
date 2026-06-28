"""
Adapters de sumarizacao (SummarizerPort).

- LocalSummarizerAdapter: resumo ABSTRATIVO com HF transformers (distilbart-cnn).
  Roda local (sem nuvem), mas baixa ~1GB de modelo na 1a vez e usa torch. Import
  preguicoso e pipeline cacheado. E o backend DEFAULT (escolha do autor) e o usado
  na avaliacao ROUGE.

- ExtractiveSummarizerAdapter: resumo EXTRATIVO simples (primeiras frases). Zero
  download, instantaneo, sem dependencias pesadas. Bom para testes/CI e como
  alternativa leve (SUMMARIZER_BACKEND=extractive).

Nota: distilbart-cnn foi treinado em ingles (CNN/DailyMail). Em portugues o resumo
e aproximado -- limitacao documentada no relatorio. Suficiente para a demo/ROUGE.
"""

from __future__ import annotations

import logging
import re

from backend.app.ports.base import SummarizerPort

logger = logging.getLogger(__name__)


class LocalSummarizerAdapter(SummarizerPort):
    """Resumo abstrativo via transformers (distilbart-cnn)."""

    nome_backend = "distilbart"  # usado para rastreabilidade na resposta

    def __init__(
        self,
        modelo: str = "sshleifer/distilbart-cnn-12-6",
        max_tokens_saida: int = 130,
        min_tokens_saida: int = 30,
    ) -> None:
        self._modelo = modelo
        self._max = max_tokens_saida
        self._min = min_tokens_saida
        self._carregado = None  # cache de (tokenizer, model) - carrega na 1a chamada

    def _carregar(self):
        """
        Carrega tokenizer + modelo seq2seq (BART) uma unica vez.

        Usamos AutoTokenizer/AutoModelForSeq2SeqLM em vez de pipeline('summarization')
        porque o nome dessa task mudou entre versoes do transformers (na v5 ela nao
        existe mais como alias). A API Auto* e estavel entre versoes.
        """
        if self._carregado is None:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # lazy
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "LocalSummarizerAdapter requer 'transformers'. Instale com "
                    "'pip install transformers' ou use SUMMARIZER_BACKEND=extractive."
                ) from exc
            logger.info("Carregando modelo de sumarizacao: %s", self._modelo)
            tokenizer = AutoTokenizer.from_pretrained(self._modelo)
            modelo = AutoModelForSeq2SeqLM.from_pretrained(self._modelo)
            self._carregado = (tokenizer, modelo)
        return self._carregado

    def resumir(self, texto: str) -> str:
        texto = (texto or "").strip()
        # textos muito curtos nao precisam (e podem quebrar o modelo): devolve como esta
        if len(texto.split()) < self._min:
            return texto

        tokenizer, modelo = self._carregar()
        # truncation/max_length=1024: limite de entrada do BART (nao estourar)
        entradas = tokenizer(
            texto, return_tensors="pt", truncation=True, max_length=1024
        )
        ids_resumo = modelo.generate(
            **entradas,
            max_length=self._max,
            min_length=self._min,
            num_beams=4,
            no_repeat_ngram_size=3,
            early_stopping=True,
        )
        return tokenizer.decode(ids_resumo[0], skip_special_tokens=True).strip()


class ExtractiveSummarizerAdapter(SummarizerPort):
    """Resumo extrativo: devolve as primeiras frases ate ~max_palavras."""

    nome_backend = "extractive"  # usado para rastreabilidade na resposta

    def __init__(self, max_frases: int = 3, max_palavras: int = 80) -> None:
        self.max_frases = max_frases
        self.max_palavras = max_palavras

    def resumir(self, texto: str) -> str:
        texto = (texto or "").strip()
        if not texto:
            return ""
        # divide em frases por pontuacao final (. ! ?) seguida de espaco
        frases = re.split(r"(?<=[.!?])\s+", texto)
        selecionadas: list[str] = []
        total_palavras = 0
        for frase in frases:
            if len(selecionadas) >= self.max_frases or total_palavras >= self.max_palavras:
                break
            selecionadas.append(frase.strip())
            total_palavras += len(frase.split())
        return " ".join(selecionadas).strip()
