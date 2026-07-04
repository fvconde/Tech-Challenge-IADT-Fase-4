"""
Adapters de analise de POSE / atividade corporal (PosePort).

- LocalPoseAdapter: MediaPipe Pose (Tasks API - PoseLandmarker), 100% local, custo zero.
  O MediaPipe devolve 33 landmarks do corpo; a "especializacao" para o nosso caso
  (sinais de estresse/defesa) esta nas HEURISTICAS geometricas deste arquivo
  (ex.: maos proximas ao rosto, bracos junto ao corpo). Isso NAO e diagnostico:
  sao indicios observaveis que a equipe deve avaliar.
  Import lazy de mediapipe/cv2: o app sobe mesmo sem essas libs; o erro so aparece
  se o adapter for realmente usado (default e mock).

- MockPoseAdapter: nao carrega modelo nem le arquivo. Devolve sinais "de mentira"
  configuraveis. Serve para testes e modo offline (igual ao mock de video).

Suporta imagem (1 inferencia) e video (amostragem de 1 frame a cada N).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

from backend.app.ports.base import DeteccaoPose, PoseAnalysisResult, PosePort
from backend.app.ports.video import EXTENSOES_IMAGEM

logger = logging.getLogger(__name__)

# Indices dos landmarks do MediaPipe Pose usados pelas heuristicas.
_NARIZ = 0
_OMBRO_ESQ, _OMBRO_DIR = 11, 12
_PULSO_ESQ, _PULSO_DIR = 15, 16
_QUADRIL_ESQ, _QUADRIL_DIR = 23, 24

# Limiares (coordenadas normalizadas 0..1 do MediaPipe).
_DIST_MAO_ROSTO = 0.18       # pulso a esta distancia do nariz => mao no rosto
_DIST_MAOS_JUNTAS = 0.12     # pulsos a esta distancia entre si => maos juntas
_VISIBILIDADE_MIN = 0.5      # ignora landmark pouco confiavel


def _dist(a, b) -> float:
    """Distancia euclidiana 2D entre dois landmarks (coords normalizadas)."""
    return math.hypot(a.x - b.x, a.y - b.y)


def _vis(landmark) -> float:
    """
    Visibilidade do landmark, robusta a None.

    A Tasks API pode devolver visibility=None; nesse caso assumimos 1.0 (visivel),
    pois o proprio detector so retornou o landmark porque o considerou presente.
    """
    v = getattr(landmark, "visibility", None)
    return 1.0 if v is None else float(v)


def _sinais_do_frame(landmarks, frame: int) -> list[DeteccaoPose]:
    """
    Traduz os landmarks de UM frame em sinais corporais de interesse.

    Heuristicas conservadoras (proxies de estresse/defesa), cada uma com uma
    confianca derivada da visibilidade dos landmarks envolvidos:
      - maos_proximas_ao_rosto: pulso perto do nariz (gesto de protecao).
      - maos_juntas_ao_corpo: pulsos proximos entre si na altura do tronco
        (auto-conforto / ansiedade).
    """
    sinais: list[DeteccaoPose] = []
    nariz = landmarks[_NARIZ]
    pulso_e, pulso_d = landmarks[_PULSO_ESQ], landmarks[_PULSO_DIR]
    vis_nariz = _vis(nariz)

    # --- maos proximas ao rosto ---
    for pulso in (pulso_e, pulso_d):
        vis_pulso = _vis(pulso)
        if vis_pulso < _VISIBILIDADE_MIN or vis_nariz < _VISIBILIDADE_MIN:
            continue
        d = _dist(pulso, nariz)
        if d <= _DIST_MAO_ROSTO:
            conf = round(min(vis_pulso, vis_nariz) * (1 - d / _DIST_MAO_ROSTO), 3)
            sinais.append(DeteccaoPose("maos_proximas_ao_rosto", max(conf, 0.1), frame))
            break  # basta uma das maos

    # --- maos juntas na altura do tronco ---
    vis_pe, vis_pd = _vis(pulso_e), _vis(pulso_d)
    if (
        vis_pe >= _VISIBILIDADE_MIN
        and vis_pd >= _VISIBILIDADE_MIN
        and _dist(pulso_e, pulso_d) <= _DIST_MAOS_JUNTAS
    ):
        conf = round(min(vis_pe, vis_pd), 3)
        sinais.append(DeteccaoPose("maos_juntas_ao_corpo", conf, frame))

    return sinais


class LocalPoseAdapter(PosePort):
    """
    Deteccao de sinais corporais com MediaPipe Pose (Tasks API), local.

    A MediaPipe 0.10.x usa a Tasks API (PoseLandmarker), que exige um arquivo de
    modelo '.task'. Ele e baixado uma unica vez do repositorio publico do Google
    (mesma ideia do auto-download do YOLO 'yolov8n.pt'); depois roda 100% offline.
    Aponte POSE_MODEL para um arquivo local para nao precisar de rede.
    """

    _URL_MODELO = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    )

    def __init__(self, modelo: str = "pose_landmarker_lite.task") -> None:
        self._caminho_modelo = modelo

    def _garantir_modelo(self) -> str:
        """Devolve o caminho do modelo, baixando-o na 1a vez se necessario."""
        p = Path(self._caminho_modelo)
        if not p.exists():
            import urllib.request  # stdlib

            logger.info("Baixando modelo MediaPipe Pose: %s", self._URL_MODELO)
            p.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(self._URL_MODELO, str(p))
        return str(p)

    def analisar(self, caminho: str, amostragem: int = 15) -> PoseAnalysisResult:
        try:
            import cv2  # import lazy
            import mediapipe as mp  # import lazy
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                PoseLandmarker,
                PoseLandmarkerOptions,
                RunningMode,
            )
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError(
                "LocalPoseAdapter requer 'mediapipe' e 'opencv-python'. Instale com "
                "'pip install mediapipe opencv-python' ou use POSE_BACKEND=mock."
            ) from exc

        modelo = self._garantir_modelo()
        eh_imagem = Path(caminho).suffix.lower() in EXTENSOES_IMAGEM
        opcoes = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=modelo),
            running_mode=RunningMode.IMAGE if eh_imagem else RunningMode.VIDEO,
        )

        sinais: list[DeteccaoPose] = []
        frames_analisados = 0
        with PoseLandmarker.create_from_options(opcoes) as landmarker:
            if eh_imagem:
                imagem = cv2.imread(caminho)
                if imagem is None:
                    raise RuntimeError(f"Nao foi possivel abrir a imagem: {caminho}")
                mp_img = self._para_mp_image(mp, cv2, imagem)
                sinais = self._sinais_do_resultado(landmarker.detect(mp_img), 0)
                frames_analisados = 1
            else:
                sinais, frames_analisados = self._processar_video(
                    landmarker, caminho, amostragem, cv2, mp
                )

        logger.info(
            "Pose analisada: %d frames amostrados, %d sinais.",
            frames_analisados, len(sinais),
        )
        return PoseAnalysisResult(
            sinais=sinais,
            frames_analisados=frames_analisados,
            backend="local_mediapipe",
        )

    @staticmethod
    def _para_mp_image(mp, cv2, imagem_bgr):
        """Converte um frame BGR (cv2) para mp.Image RGB (contiguo)."""
        import numpy as np

        rgb = np.ascontiguousarray(cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB))
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    @staticmethod
    def _sinais_do_resultado(resultado, frame: int) -> list[DeteccaoPose]:
        """Extrai sinais da 1a pessoa detectada (Tasks API: pose_landmarks e lista de listas)."""
        poses = getattr(resultado, "pose_landmarks", None)
        if not poses:
            return []  # nenhuma pessoa detectada neste frame
        return _sinais_do_frame(poses[0], frame)

    def _processar_video(
        self, landmarker, caminho: str, amostragem: int, cv2, mp
    ) -> tuple[list[DeteccaoPose], int]:
        captura = cv2.VideoCapture(caminho)
        if not captura.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir o video: {caminho}")

        fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
        sinais: list[DeteccaoPose] = []
        frames_analisados = 0
        indice = 0
        amostragem = max(1, amostragem)  # evita divisao por zero
        try:
            while True:
                ok, frame = captura.read()
                if not ok:
                    break
                if indice % amostragem == 0:
                    mp_img = self._para_mp_image(mp, cv2, frame)
                    # timestamp monotonico em ms (exigido pelo modo VIDEO)
                    ts_ms = int(indice / fps * 1000)
                    resultado = landmarker.detect_for_video(mp_img, ts_ms)
                    sinais.extend(self._sinais_do_resultado(resultado, indice))
                    frames_analisados += 1
                indice += 1
        finally:
            captura.release()
        return sinais, frames_analisados


class MockPoseAdapter(PosePort):
    """
    Adapter de pose falso (sem modelo, sem leitura de arquivo).

    Recebe sinais pre-definidos e os devolve. Util para testes e modo offline
    sem mediapipe/cv2. Sem sinais => nenhum risco de pose (comportamento neutro).
    """

    def __init__(
        self,
        sinais: list[DeteccaoPose] | None = None,
        frames_analisados: int = 1,
    ) -> None:
        self._sinais = sinais or []
        self._frames = frames_analisados

    def analisar(self, caminho: str, amostragem: int = 15) -> PoseAnalysisResult:
        return PoseAnalysisResult(
            sinais=list(self._sinais),
            frames_analisados=self._frames,
            backend="mock",
        )
