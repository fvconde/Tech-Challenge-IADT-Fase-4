"""
Adapters de analise de EMOCAO facial (EmotionPort).

- LocalEmotionAdapter: DeepFace.analyze(actions=["emotion"]), 100% local, custo zero.
  DeepFace detecta o rosto e estima a emocao aparente (angry, disgust, fear, happy,
  sad, surprise, neutral). Isso NAO e diagnostico: e a emocao aparente do rosto
  naquele instante; a decisao de risco (emocao negativa sustentada) fica nas regras
  (services/video/emotion_rules.py).
  Import lazy de deepface/cv2: o app sobe mesmo sem essas libs; o erro so aparece
  se o adapter for realmente usado (default e mock). DeepFace baixa pesos (~alguns
  MB) na 1a execucao.

- MockEmotionAdapter: nao carrega modelo nem le arquivo. Devolve emocoes "de mentira"
  configuraveis. Serve para testes e modo offline.

Suporta imagem (1 inferencia) e video (amostragem de 1 frame a cada N).
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.ports.base import DeteccaoEmocao, EmotionAnalysisResult, EmotionPort
from backend.app.ports.video import EXTENSOES_IMAGEM

logger = logging.getLogger(__name__)


class LocalEmotionAdapter(EmotionPort):
    """Analise de emocao facial com DeepFace, rodando localmente."""

    suporta_anotacao_video = True

    def analisar(self, caminho: str, amostragem: int = 15) -> EmotionAnalysisResult:
        try:
            import cv2  # import lazy
            from deepface import DeepFace  # import lazy
        except ImportError as exc:  # pragma: no cover - depende do ambiente
            raise RuntimeError(
                "LocalEmotionAdapter requer 'deepface' e 'opencv-python'. Instale com "
                "'pip install deepface opencv-python' ou use EMOTION_BACKEND=mock."
            ) from exc

        sufixo = Path(caminho).suffix.lower()
        if sufixo in EXTENSOES_IMAGEM:
            imagem = cv2.imread(caminho)
            if imagem is None:
                raise RuntimeError(f"Nao foi possivel abrir a imagem: {caminho}")
            emocoes = self._analisar_frame(DeepFace, imagem, 0)
            frames_analisados = 1
        else:
            emocoes, frames_analisados = self._analisar_video(
                DeepFace, caminho, amostragem, cv2
            )

        logger.info(
            "Emocao analisada: %d frames amostrados, %d rostos.",
            frames_analisados, len(emocoes),
        )
        return EmotionAnalysisResult(
            emocoes=emocoes,
            frames_analisados=frames_analisados,
            backend="local_deepface",
        )

    @staticmethod
    def _analisar_frame(DeepFace, imagem_bgr, frame: int) -> list[DeteccaoEmocao]:
        """
        Roda o DeepFace em UM frame e extrai a emocao dominante de cada rosto.

        enforce_detection=False: quando nao ha rosto, o DeepFace nao lanca erro
        (devolve resultado de baixa confianca); filtramos abaixo.
        """
        try:
            resultados = DeepFace.analyze(
                imagem_bgr,
                actions=["emotion"],
                enforce_detection=False,
                silent=True,
            )
        except Exception:  # pragma: no cover - frame sem rosto / erro pontual
            logger.debug("DeepFace falhou no frame %d (ignorado).", frame, exc_info=True)
            return []

        # DeepFace pode devolver dict (1 rosto) ou list[dict] (varios rostos).
        if isinstance(resultados, dict):
            resultados = [resultados]

        emocoes: list[DeteccaoEmocao] = []
        for r in resultados:
            dominante = r.get("dominant_emotion")
            mapa = r.get("emotion", {})
            if not dominante or not mapa:
                continue
            # DeepFace devolve scores 0..100; normaliza para 0..1.
            score = round(float(mapa.get(dominante, 0.0)) / 100.0, 3)
            emocoes.append(DeteccaoEmocao(emocao=dominante, score=score, frame=frame))
        return emocoes

    def _analisar_video(
        self, DeepFace, caminho: str, amostragem: int, cv2
    ) -> tuple[list[DeteccaoEmocao], int]:
        captura = cv2.VideoCapture(caminho)
        if not captura.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir o video: {caminho}")

        emocoes: list[DeteccaoEmocao] = []
        frames_analisados = 0
        indice = 0
        amostragem = max(1, amostragem)
        try:
            while True:
                ok, frame = captura.read()
                if not ok:
                    break
                if indice % amostragem == 0:
                    emocoes.extend(self._analisar_frame(DeepFace, frame, indice))
                    frames_analisados += 1
                indice += 1
        finally:
            captura.release()
        return emocoes, frames_analisados


class MockEmotionAdapter(EmotionPort):
    """
    Adapter de emocao falso (sem modelo, sem leitura de arquivo).

    Recebe emocoes pre-definidas e as devolve. Util para testes e modo offline
    sem deepface/cv2. Sem emocoes => nenhum risco emocional (comportamento neutro).
    """

    def __init__(
        self,
        emocoes: list[DeteccaoEmocao] | None = None,
        frames_analisados: int = 1,
    ) -> None:
        self._emocoes = emocoes or []
        self._frames = frames_analisados

    def analisar(self, caminho: str, amostragem: int = 15) -> EmotionAnalysisResult:
        return EmotionAnalysisResult(
            emocoes=list(self._emocoes),
            frames_analisados=self._frames,
            backend="mock",
        )
