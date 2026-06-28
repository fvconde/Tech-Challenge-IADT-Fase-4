"""
Avalia a sumarizacao (distilbart) com a metrica ROUGE.

Compara o resumo gerado pelo modelo contra um RESUMO DE REFERENCIA sintetico
(escrito a mao em data/samples/laudo_exemplo_resumo_ref.txt). Imprime ROUGE-1/2/L.

ROUGE mede sobreposicao de n-gramas entre o resumo gerado e a referencia:
- ROUGE-1: palavras (unigramas) em comum.
- ROUGE-2: pares de palavras (bigramas) em comum.
- ROUGE-L: maior subsequencia comum (fluencia/ordem).

ATENCAO: distilbart-cnn foi treinado em INGLES; em portugues o resultado e modesto.
O objetivo aqui e ter um numero reprodutivel para o relatorio, nao um SOTA.

Uso (precisa de transformers + rouge-score instalados):
    python scripts/avaliar_rouge.py
"""

from __future__ import annotations

import pathlib
import sys

# garante que 'backend' seja importavel, rodando de qualquer lugar
RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.app.ports.summarizer import LocalSummarizerAdapter  # noqa: E402


def main() -> None:
    try:
        from rouge_score import rouge_scorer
    except ImportError:
        raise SystemExit("Instale 'rouge-score' (pip install rouge-score) para avaliar.")

    laudo = (RAIZ / "data/samples/laudo_exemplo.txt").read_text(encoding="utf-8")
    referencia = (RAIZ / "data/samples/laudo_exemplo_resumo_ref.txt").read_text(
        encoding="utf-8"
    ).strip()

    print("Gerando resumo com distilbart (pode baixar ~1GB na 1a vez)...")
    resumo = LocalSummarizerAdapter().resumir(laudo)
    print("\n--- Resumo gerado ---")
    print(resumo)
    print("\n--- Resumo de referencia ---")
    print(referencia)

    scorer = rouge_scorer.RougeScorer(
        ["rouge1", "rouge2", "rougeL"], use_stemmer=True
    )
    scores = scorer.score(referencia, resumo)

    print("\n--- ROUGE (F1) ---")
    for chave in ("rouge1", "rouge2", "rougeL"):
        print(f"{chave}: {scores[chave].fmeasure:.3f}")


if __name__ == "__main__":
    main()
