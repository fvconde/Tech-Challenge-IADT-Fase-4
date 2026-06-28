"""
Gera um VIDEO SINTETICO curto para testar o pipeline de video (sem PHI).

Por que um gerador (em vez de versionar um .mp4)? Mantem o repositorio leve e o
exemplo reproduzivel, mesmo padrao do WAV de audio da Sessao 1.

Uso:
    python scripts/gerar_video_exemplo.py
    python scripts/gerar_video_exemplo.py --segundos 3 --fps 12

Se existir uma imagem base (default: data/samples/demo_yolo.jpg, baixada pelo
notebook 01), o video e montado a partir dela -> o YOLO detecta objetos reais.
Caso contrario, gera frames sinteticos (retangulo em movimento) so para exercitar
a amostragem de frames.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def gerar(
    saida: str,
    segundos: int = 2,
    fps: int = 10,
    largura: int = 640,
    altura: int = 480,
    fonte: str | None = None,
) -> None:
    destino = Path(saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    # codec mp4v: amplamente disponivel no OpenCV, sem dependencia externa
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(destino), fourcc, fps, (largura, altura))

    base = None
    if fonte and Path(fonte).exists():
        img = cv2.imread(str(fonte))
        if img is not None:
            base = cv2.resize(img, (largura, altura))
            print("Usando imagem base:", fonte)

    total = max(1, segundos * fps)
    for i in range(total):
        if base is not None:
            frame = base.copy()
        else:
            # fundo cinza escuro + retangulo vermelho que atravessa a tela
            frame = np.full((altura, largura, 3), 30, dtype=np.uint8)
        x = int((largura - 100) * i / max(1, total - 1))
        cv2.rectangle(frame, (x, 200), (x + 100, 300), (0, 0, 255), -1)
        writer.write(frame)

    writer.release()
    print(f"Video gerado: {destino} ({total} frames, {fps} fps)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera video sintetico de exemplo")
    parser.add_argument("--saida", default="data/samples/video_exemplo.mp4")
    parser.add_argument("--segundos", type=int, default=2)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument(
        "--fonte",
        default="data/samples/demo_yolo.jpg",
        help="imagem base opcional (se existir, o video usa objetos reais)",
    )
    args = parser.parse_args()
    gerar(args.saida, args.segundos, args.fps, fonte=args.fonte)
