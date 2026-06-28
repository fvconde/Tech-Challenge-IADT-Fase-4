"""
Gera um PDF de LAUDO sintetico para testar o pipeline de documentos (SEM PHI).

Mesmo padrao do gerador de video: mantem o repositorio leve (o PDF e gitignored) e
reproduzivel. O texto-fonte vem de data/samples/laudo_exemplo.txt.

Uso:
    python scripts/gerar_laudo_exemplo.py
    python scripts/gerar_laudo_exemplo.py --fonte data/samples/laudo_exemplo.txt --saida data/samples/laudo_exemplo.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def gerar(fonte: str, saida: str) -> None:
    texto = Path(fonte).read_text(encoding="utf-8")
    destino = Path(saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(destino), pagesize=A4)
    estilos = getSampleStyleSheet()
    elementos = []

    # cada paragrafo do .txt (separados por linha em branco) vira um Paragraph,
    # que o reportlab quebra em linhas automaticamente.
    for bloco in texto.split("\n\n"):
        bloco = bloco.strip()
        if not bloco:
            continue
        elementos.append(Paragraph(bloco, estilos["Normal"]))
        elementos.append(Spacer(1, 12))

    doc.build(elementos)
    print(f"PDF de laudo gerado: {destino}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera PDF de laudo sintetico")
    parser.add_argument("--fonte", default="data/samples/laudo_exemplo.txt")
    parser.add_argument("--saida", default="data/samples/laudo_exemplo.pdf")
    args = parser.parse_args()
    gerar(args.fonte, args.saida)
