"""Acopla (mux) uma trilha de AUDIO num video, para testar a extracao/transcricao.

Usa o ffmpeg embutido do imageio-ffmpeg (dependencia da moviepy) -> NAO exige ffmpeg no PATH.
Se o audio couber no video, corta no menor (-shortest, saida limpa); senao preserva a fala
inteira (sem -shortest). O video nao e recodificado (copia de stream).

Uso:
    python scripts/acoplar_audio.py \
        --video data/samples/paciente_demoV2.mp4 \
        --audio data/samples/fala.mp3 \
        --saida data/samples/paciente_demoV2_audio.mp4
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _duracao_video(caminho: str) -> float:
    try:
        from moviepy import VideoFileClip  # moviepy 2.x
    except ImportError:
        from moviepy.editor import VideoFileClip  # moviepy 1.x
    clip = VideoFileClip(caminho)
    try:
        return float(clip.duration)
    finally:
        clip.close()


def _duracao_audio(caminho: str) -> float:
    try:
        from moviepy import AudioFileClip
    except ImportError:
        from moviepy.editor import AudioFileClip
    clip = AudioFileClip(caminho)
    try:
        return float(clip.duration)
    finally:
        clip.close()


def acoplar(video: str, audio: str, saida: str) -> None:
    try:
        import imageio_ffmpeg
    except ImportError:
        sys.exit("imageio-ffmpeg ausente (vem com a moviepy). Rode: pip install moviepy")

    destino = Path(saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    dv, da = _duracao_video(video), _duracao_audio(audio)
    print(f"duracoes: video={dv:.2f}s  audio={da:.2f}s")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-i", video, "-i", audio,
           "-c:v", "copy", "-c:a", "aac",
           "-map", "0:v:0", "-map", "1:a:0"]
    if da <= dv:
        cmd.append("-shortest")  # audio cabe -> saida limpa na duracao do video
    cmd.append(str(destino))

    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        sys.exit("Falha no ffmpeg:\n" + resultado.stderr[-2000:])
    print(f"Video com audio gerado: {destino}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Acopla audio num video (mux, via imageio-ffmpeg)")
    parser.add_argument("--video", default="data/samples/paciente_demoV2.mp4")
    parser.add_argument("--audio", default="data/samples/fala.mp3")
    parser.add_argument("--saida", default="data/samples/paciente_demoV2_audio.mp4")
    args = parser.parse_args()
    acoplar(args.video, args.audio, args.saida)
