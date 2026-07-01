"""
Adapters de analise de video (VideoPort).

- LocalVideoAdapter: YOLOv8 (ultralytics) com modelo PRE-TREINADO yolov8n.pt.
  100% local, custo zero, SEM treino customizado. A "especializacao" para o nosso
  caso (objetos suspeitos de automutilacao) NAO esta no modelo, e sim nas REGRAS DE
  RISCO do pos-processamento (services/video/risk_rules.py): o modelo detecta classes
  COCO genericas (knife, scissors, ...) e nos decidimos o que e risco.
  Import lazy de ultralytics/cv2: o app sobe mesmo sem essas libs instaladas; o erro
  so aparece se o adapter de video for realmente usado.

- MockVideoAdapter: nao carrega modelo nem le arquivo. Devolve deteccoes "de mentira"
  configuraveis. Serve para testes e modo offline (igual ao mock de audio).

Suporta imagem (1 inferencia) e video (amostragem de 1 frame a cada N, para nao pesar).
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.ports.base import (
    DeteccaoVisual,
    VideoAnalysisResult,
    VideoPort,
)

logger = logging.getLogger(__name__)

# Extensoes tratadas como imagem (o resto e tratado como video).
EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class LocalVideoAdapter(VideoPort):
    """Deteccao de objetos com YOLOv8 pre-treinado, rodando localmente."""

    def __init__(self, modelo: str = "yolov8n.pt") -> None:
        # Guardamos so o nome do modelo; o carregamento real e preguicoso
        # (lazy) para nao pagar o custo de importar torch na subida do app.
        self._nome_modelo = modelo
        self._modelo = None  # cache do modelo carregado

    def _carregar_modelo(self):
        """Carrega o YOLO uma unica vez (cache)."""
        if self._modelo is None:
            try:
                from ultralytics import YOLO  # import lazy
            except ImportError as exc:  # pragma: no cover - depende do ambiente
                raise RuntimeError(
                    "LocalVideoAdapter requer 'ultralytics'. Instale com "
                    "'pip install ultralytics opencv-python' ou use VIDEO_BACKEND=mock."
                ) from exc
            logger.info("Carregando modelo YOLOv8: %s", self._nome_modelo)
            self._modelo = YOLO(self._nome_modelo)
        return self._modelo

    def analisar(
        self,
        caminho: str,
        classes_foco: list[str],
        amostragem: int = 15,
        conf: float = 0.25,
    ) -> VideoAnalysisResult:
        sufixo = Path(caminho).suffix.lower()
        if sufixo in EXTENSOES_IMAGEM:
            return self._analisar_imagem(caminho, classes_foco, conf)
        return self._analisar_video(caminho, classes_foco, amostragem, conf)

    # ---------------------- imagem ----------------------
    def _analisar_imagem(
        self, caminho: str, classes_foco: list[str], conf: float
    ) -> VideoAnalysisResult:
        modelo = self._carregar_modelo()
        resultados = modelo(caminho, conf=conf, verbose=False)
        deteccoes = self._extrair_deteccoes(resultados[0], modelo.names, frame=0)
        return VideoAnalysisResult(
            deteccoes=deteccoes,
            frames_analisados=1,
            backend=f"local_{Path(self._nome_modelo).stem}",
            classes_foco=classes_foco,
            imagem_anotada_b64=self._encode_anotada(resultados[0]),
        )

    # ---------------------- video ----------------------
    def _analisar_video(
        self, caminho: str, classes_foco: list[str], amostragem: int, conf: float
    ) -> VideoAnalysisResult:
        try:
            import cv2  # import lazy
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Analise de video requer 'opencv-python' (cv2). "
                "Instale com 'pip install opencv-python'."
            ) from exc

        modelo = self._carregar_modelo()
        captura = cv2.VideoCapture(caminho)
        if not captura.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir o video: {caminho}")

        deteccoes: list[DeteccaoVisual] = []
        frames_analisados = 0
        indice = 0
        amostragem = max(1, amostragem)  # evita divisao por zero / loop infinito

        # guarda o frame de MAIOR confianca para anotar (imagem representativa da demo)
        melhor_conf = -1.0
        melhor_resultado = None

        try:
            while True:
                ok, frame = captura.read()
                if not ok:
                    break  # acabou o video
                # processa 1 frame a cada 'amostragem' (reduz custo)
                if indice % amostragem == 0:
                    resultados = modelo(frame, conf=conf, verbose=False)
                    deteccoes.extend(
                        self._extrair_deteccoes(resultados[0], modelo.names, frame=indice)
                    )
                    # confianca maxima neste frame
                    confs = [float(b.conf[0]) for b in resultados[0].boxes]
                    if confs and max(confs) > melhor_conf:
                        melhor_conf = max(confs)
                        melhor_resultado = resultados[0]
                    frames_analisados += 1
                indice += 1
        finally:
            captura.release()

        logger.info(
            "Video analisado: %d frames amostrados, %d deteccoes.",
            frames_analisados, len(deteccoes),
        )
        return VideoAnalysisResult(
            deteccoes=deteccoes,
            frames_analisados=frames_analisados,
            backend=f"local_{Path(self._nome_modelo).stem}",
            classes_foco=classes_foco,
            imagem_anotada_b64=(
                self._encode_anotada(melhor_resultado) if melhor_resultado else None
            ),
        )

    @staticmethod
    def _extrair_deteccoes(resultado, nomes: dict, frame: int) -> list[DeteccaoVisual]:
        """Converte as boxes do YOLO em DeteccaoVisual (dominio)."""
        saida: list[DeteccaoVisual] = []
        for box in resultado.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            saida.append(
                DeteccaoVisual(classe=nomes[cls], confianca=round(conf, 3), frame=frame)
            )
        return saida

    @staticmethod
    def _encode_anotada(resultado_yolo) -> str | None:
        """
        Desenha as bounding boxes (result.plot()) e devolve a imagem como JPEG
        em base64. E APENAS apresentacao: qualquer falha vira None (nao pode
        quebrar o endpoint de analise).
        """
        try:
            import base64

            import cv2  # disponivel junto do ultralytics

            arr = resultado_yolo.plot()  # ndarray BGR com as boxes desenhadas
            ok, buffer = cv2.imencode(".jpg", arr)
            if not ok:
                return None
            return base64.b64encode(buffer.tobytes()).decode("ascii")
        except Exception:  # pragma: no cover - anotacao e so apresentacao
            logger.warning("Falha ao gerar imagem anotada.", exc_info=True)
            return None


class MockVideoAdapter(VideoPort):
    """
    Adapter de video falso (sem modelo, sem leitura de arquivo).

    Recebe no construtor uma lista de deteccoes pre-definidas e simplesmente as
    devolve. Util para testes e para rodar o fluxo offline sem ultralytics/cv2.
    """

    def __init__(
        self,
        deteccoes: list[DeteccaoVisual] | None = None,
        frames_analisados: int = 1,
        imagem_anotada_b64: str | None = None,
    ) -> None:
        self._deteccoes = deteccoes or []
        self._frames = frames_analisados
        self._imagem_anotada_b64 = imagem_anotada_b64

    def analisar(
        self,
        caminho: str,
        classes_foco: list[str],
        amostragem: int = 15,
        conf: float = 0.25,
    ) -> VideoAnalysisResult:
        return VideoAnalysisResult(
            deteccoes=list(self._deteccoes),
            frames_analisados=self._frames,
            backend="mock",
            classes_foco=classes_foco,
            imagem_anotada_b64=self._imagem_anotada_b64,
        )
