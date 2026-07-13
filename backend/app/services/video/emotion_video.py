"""
Anotacao de EMOCOES em video (apresentacao) + agregacao do perfil emocional.

Gera um NOVO video no qual, a cada frame, sao desenhados a caixa do rosto
(``cv2.rectangle``) e o rotulo da emocao aparente (``cv2.putText``); e devolve
tambem o "perfil emocional" agregado (media por emocao) que alimenta o grafico em
HEXAGONO do frontend.

Para nao rodar o modelo em TODO frame (caro), o DeepFace roda a cada N frames
(``amostragem``) e a ultima deteccao e reaproveitada nos frames intermediarios --
assim o video sai fluido. O ``tqdm`` mostra o progresso do desenho no console do
servidor (``desc="Processando video"``), como pedido.

Esta e uma camada de PRESENTACAO (do mesmo jeito que o LocalVideoAdapter ja desenha
as boxes do YOLO em ``_encode_anotada``): por isso chama cv2/DeepFace/tqdm
diretamente, com import lazy, e qualquer lib ausente vira ``RuntimeError`` com
mensagem clara (o router decide o status HTTP).

Postura etica: NAO e diagnostico -- e a emocao aparente do rosto naquele instante.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.app.ports.base import DeteccaoEmocao

logger = logging.getLogger(__name__)

# As 7 emocoes do DeepFace. O rotulo desenhado NO VIDEO precisa ser ASCII: as fontes
# Hershey do OpenCV (cv2.putText) nao renderizam acento (viram '?'). O rotulo PT
# acentuado (para o HTML do frontend) fica no mapa _ROTULO_PT.
_ROTULO_ASCII = {
    "angry": "raiva",
    "disgust": "aversao",
    "fear": "medo",
    "sad": "tristeza",
    "surprise": "surpresa",
    "neutral": "neutro",
    "happy": "alegria",
}
_ROTULO_PT = {
    "angry": "raiva",
    "disgust": "aversão",
    "fear": "medo",
    "sad": "tristeza",
    "surprise": "surpresa",
    "neutral": "neutro",
    "happy": "alegria",
}
# Emocoes de valencia NEGATIVA (as clinicamente relevantes p/ indicio de risco).
_NEGATIVAS = {"angry", "disgust", "fear", "sad"}
# Eixos do hexagono: as 6 emocoes SEM 'happy' (a unica positiva), em ordem agradavel
# de leitura (negativas agrupadas, depois surpresa/neutro).
_EIXOS_HEXAGONO = ["fear", "sad", "angry", "disgust", "surprise", "neutral"]


@dataclass
class PerfilEmocao:
    """Um eixo do hexagono: intensidade media de uma emocao no video."""
    emocao: str      # rotulo PT (acentuado) exibido no hexagono
    valor: float     # 0..1 (media da emocao nos frames em que houve rosto)
    negativa: bool


@dataclass
class FrameEmocao:
    """Emocao dominante de um frame amostrado (para a faixa/timeline)."""
    frame: int
    tempo_s: float
    emocao: str      # rotulo PT
    score: float


@dataclass
class ResultadoEmocaoVideo:
    """Resultado da anotacao: caminho do video gerado + perfil + timeline."""
    caminho_saida: str
    fps: float
    frames_total: int
    frames_analisados: int   # frames em que o DeepFace efetivamente rodou (amostrados)
    frames_com_rosto: int
    perfil: list[PerfilEmocao]
    timeline: list[FrameEmocao]
    dominante_geral: str     # rotulo PT da emocao dominante no video inteiro
    # deteccoes BRUTAS (chave em ingles do DeepFace, 1 por rosto/frame amostrado):
    # alimentam avaliar_risco_emocao SEM uma segunda passada do modelo.
    deteccoes: list[DeteccaoEmocao] = field(default_factory=list)
    backend: str = "local_deepface"


def anotar_video_emocoes(
    caminho_entrada: str,
    caminho_saida: str,
    amostragem: int = 15,
) -> ResultadoEmocaoVideo:
    """
    Le ``caminho_entrada``, desenha rosto+emocao por frame e grava ``caminho_saida``
    (H.264/MP4 -- codec que toca nativo em qualquer navegador). Devolve o perfil
    agregado.

    O cv2 le e DESENHA os frames (rectangle/putText), mas quem CODIFICA o video e o
    imageio (com o ffmpeg embutido no imageio-ffmpeg, ja instalado com o moviepy):
    o cv2.VideoWriter desta build nao gera VP8/H.264 valido (produz arquivo vazio ou
    falha ao iniciar o encoder), entao delegamos a escrita ao ffmpeg via imageio.
    """
    try:
        import cv2  # import lazy
        import imageio  # import lazy (ffmpeg embutido via imageio-ffmpeg)
        from deepface import DeepFace  # import lazy
        from tqdm import tqdm  # import lazy
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "Anotacao de emocao requer 'deepface', 'opencv-python', 'imageio' e "
            "'tqdm'. Instale-os (ou EMOTION_BACKEND=mock desliga o recurso)."
        ) from exc

    captura = cv2.VideoCapture(caminho_entrada)
    if not captura.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {caminho_entrada}")

    fps = captura.get(cv2.CAP_PROP_FPS)
    if not fps or fps != fps or fps <= 1e-3:  # 0 ou NaN -> assume 25
        fps = 25.0
    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    altura = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))

    # H.264 (libx264) em MP4, pixel format yuv420p: o par que TODO navegador toca.
    # macro_block_size=1 evita o redimensionamento automatico do imageio; garantimos
    # dimensoes pares (exigencia do yuv420p) cortando 1px quando impar, no laco.
    try:
        escritor = imageio.get_writer(
            caminho_saida,
            fps=fps,
            codec="libx264",
            quality=8,
            macro_block_size=1,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
        )
    except Exception as exc:  # ffmpeg ausente / erro ao abrir o encoder
        captura.release()
        raise RuntimeError(
            f"Falha ao iniciar o codificador de video (ffmpeg/imageio): {exc}"
        ) from exc

    amostragem = max(1, amostragem)
    soma = {k: 0.0 for k in _ROTULO_ASCII}       # soma dos scores por emocao
    frames_com_rosto = 0
    frames_analisados = 0
    timeline: list[FrameEmocao] = []
    deteccoes: list[DeteccaoEmocao] = []
    caixas_atuais: list[tuple] = []              # reaproveitadas entre amostras
    idx = 0

    # tqdm sobre a contagem de frames (quando conhecida); iter(int, 1) e um
    # iterador infinito usado quando o container nao informa o total.
    frames_range = range(total) if total > 0 else iter(int, 1)
    try:
        for _ in tqdm(frames_range, desc="Processando video"):
            ok, frame = captura.read()
            if not ok:
                break
            if idx % amostragem == 0:
                caixas_atuais = []
                faces = _analisar_frame(DeepFace, frame, largura, altura)
                if faces:
                    frames_com_rosto += 1
                    principal = faces[0]  # rosto mais "forte" para a timeline
                    for chave, valor in principal["dist"].items():
                        soma[chave] += valor
                    timeline.append(
                        FrameEmocao(
                            frame=idx,
                            tempo_s=round(idx / fps, 2),
                            emocao=_ROTULO_PT[principal["dominante"]],
                            score=round(principal["dist"][principal["dominante"]], 3),
                        )
                    )
                    for f in faces:
                        cor = _cor_emocao(f["dominante"])
                        pct = f["dist"][f["dominante"]] * 100.0
                        texto = f"{_ROTULO_ASCII[f['dominante']]} {pct:.0f}%"
                        caixas_atuais.append((f["x"], f["y"], f["w"], f["h"], texto, cor))
                        deteccoes.append(
                            DeteccaoEmocao(
                                emocao=f["dominante"],
                                score=round(f["dist"][f["dominante"]], 3),
                                frame=idx,
                            )
                        )
                frames_analisados += 1
            _desenhar(cv2, frame, caixas_atuais)
            # imageio grava em RGB; corta p/ dimensoes pares (exigencia do yuv420p)
            h, w = frame.shape[:2]
            frame_par = frame[: h - (h % 2), : w - (w % 2)]
            escritor.append_data(cv2.cvtColor(frame_par, cv2.COLOR_BGR2RGB))
            idx += 1
    finally:
        captura.release()
        try:
            escritor.close()
        except Exception:  # pragma: no cover
            pass

    denom = max(1, frames_com_rosto)
    perfil = [
        PerfilEmocao(
            emocao=_ROTULO_PT[k],
            valor=round(soma[k] / denom, 3),
            negativa=k in _NEGATIVAS,
        )
        for k in _EIXOS_HEXAGONO
    ]
    dominante = max(soma, key=soma.get) if frames_com_rosto else "neutral"

    logger.info(
        "Video anotado: %d frames (%d amostrados, %d com rosto) -> %s",
        idx, frames_analisados, frames_com_rosto, caminho_saida,
    )
    return ResultadoEmocaoVideo(
        caminho_saida=caminho_saida,
        fps=round(fps, 2),
        frames_total=idx,
        frames_analisados=frames_analisados,
        frames_com_rosto=frames_com_rosto,
        perfil=perfil,
        timeline=timeline,
        dominante_geral=_ROTULO_PT[dominante],
        deteccoes=deteccoes,
    )


def _analisar_frame(DeepFace, frame_bgr, largura: int, altura: int) -> list[dict]:
    """
    Roda o DeepFace em UM frame e devolve os rostos encontrados com a distribuicao
    das 7 emocoes (0..1). Frames sem rosto real sao descartados (enforce_detection
    =False faz o DeepFace nunca lancar erro: filtramos pelo face_confidence/regiao).
    """
    try:
        resultados = DeepFace.analyze(
            frame_bgr, actions=["emotion"], enforce_detection=False, silent=True
        )
    except Exception:  # pragma: no cover - frame problematico e ignorado
        return []
    if isinstance(resultados, dict):
        resultados = [resultados]

    faces: list[dict] = []
    for r in resultados:
        regiao = r.get("region") or {}
        x, y = int(regiao.get("x", 0)), int(regiao.get("y", 0))
        w, h = int(regiao.get("w", 0)), int(regiao.get("h", 0))
        conf = float(r.get("face_confidence", 0) or 0)
        mapa = r.get("emotion") or {}
        dominante = r.get("dominant_emotion")
        if not mapa or not dominante or w <= 0 or h <= 0:
            continue
        # sem rosto: DeepFace devolve a imagem inteira e/ou face_confidence 0
        if conf <= 0 and w >= largura and h >= altura:
            continue
        dist = {k: max(0.0, float(mapa.get(k, 0.0)) / 100.0) for k in _ROTULO_ASCII}
        faces.append(
            {"x": x, "y": y, "w": w, "h": h, "dominante": dominante, "dist": dist}
        )
    return faces


def _cor_emocao(emocao: str) -> tuple[int, int, int]:
    """Cor BGR do retangulo/rotulo: vermelho=negativa, verde=alegria, cinza=neutro."""
    if emocao in _NEGATIVAS:
        return (42, 35, 180)     # ~ #b4232a (severidade alta)
    if emocao == "happy":
        return (77, 122, 31)     # ~ #1f7a4d (verde clinico)
    return (150, 146, 127)       # cinza-petroleo (neutro/surpresa)


def _desenhar(cv2, frame, caixas: list[tuple]) -> None:
    """Desenha cada caixa (rosto) + rotulo com fundo solido para legibilidade."""
    for (x, y, w, h, texto, cor) in caixas:
        cv2.rectangle(frame, (x, y), (x + w, y + h), cor, 2)
        (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        ytop = max(0, y - th - 10)
        cv2.rectangle(frame, (x, ytop), (x + tw + 8, ytop + th + 8), cor, -1)
        cv2.putText(
            frame, texto, (x + 4, ytop + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA,
        )
