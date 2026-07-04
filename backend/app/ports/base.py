"""
Interfaces (ports) e tipos de dados do dominio.

Ideia central (injecao de dependencia, como no .NET):
- Definimos CONTRATOS abstratos (classes com @abstractmethod).
- Cada contrato tem >= 1 implementacao concreta (adapter):
    * uma LOCAL (default, custo zero, sem nuvem) e
    * opcionalmente uma CLOUD (AWS), usada so na demo final.
- O resto do sistema depende SO da interface, nunca da implementacao.
  Assim conseguimos trocar local <-> cloud mudando uma variavel de ambiente,
  sem alterar os services nem os routers.

Os tipos de resultado abaixo sao @dataclass (puro Python) de proposito:
a camada de dominio nao deve depender do FastAPI/Pydantic. A conversao para
schemas de API acontece em backend/app/models/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tipos de dados (resultados das portas)
# ---------------------------------------------------------------------------
@dataclass
class TranscriptionResult:
    """Resultado de uma transcricao de audio para texto."""
    texto: str
    idioma: str
    backend: str                 # qual adapter produziu (ex.: "recognize_google")
    confianca: float | None = None


@dataclass
class SentimentResult:
    """Sentimento agregado de um texto."""
    rotulo: str                  # "positivo" | "neutro" | "negativo"
    score: float                 # -1.0 (muito negativo) .. +1.0 (muito positivo)
    backend: str = "local"


@dataclass
class Entidade:
    """Entidade extraida do texto (sintoma, medicamento, etc.)."""
    texto: str
    tipo: str                    # ex.: "sintoma", "medicamento", "tempo"


@dataclass
class NlpResult:
    """Resultado completo de analise de linguagem natural."""
    sentimento: SentimentResult
    entidades: list[Entidade] = field(default_factory=list)


@dataclass
class DeteccaoCategoria:
    """
    Uma categoria de risco detectada, com score e evidencias.

    E o tipo COMUM a todas as modalidades (texto, audio e video). Por isso vive
    aqui na camada de dominio: a fusao multimodal combina listas deste tipo sem
    saber de qual modalidade vieram.
    """
    categoria: str               # ex.: "ansiedade", "objeto_suspeito_automutilacao"
    score: float                 # 0.0 .. 1.0 (intensidade dos indicios)
    evidencias: list[str] = field(default_factory=list)  # rastreabilidade


@dataclass
class DeteccaoVisual:
    """Uma deteccao de objeto em um frame de video/imagem (YOLOv8)."""
    classe: str                  # nome da classe COCO (ex.: "knife", "scissors")
    confianca: float             # 0.0 .. 1.0
    frame: int = 0               # indice do frame onde apareceu (0 para imagem)


@dataclass
class VideoAnalysisResult:
    """Resultado da analise de um video/imagem."""
    deteccoes: list[DeteccaoVisual] = field(default_factory=list)
    frames_analisados: int = 0   # quantos frames foram efetivamente processados
    backend: str = "local"       # qual adapter produziu (ex.: "local_yolov8n")
    classes_foco: list[str] = field(default_factory=list)  # classes monitoradas
    # imagem com bounding boxes desenhadas (JPEG em base64) - apenas apresentacao
    imagem_anotada_b64: str | None = None


@dataclass
class DeteccaoPose:
    """
    Um sinal corporal (postura/gesto) detectado num frame via MediaPipe Pose.

    NAO e diagnostico: e um indicio observavel (ex.: bracos protegendo o rosto,
    corpo encolhido) que a equipe deve avaliar. O texto do 'sinal' e legivel para
    virar evidencia rastreavel na fusao.
    """
    sinal: str                   # ex.: "bracos_protegendo_rosto", "corpo_encolhido"
    confianca: float             # 0.0 .. 1.0 (heuristica sobre os landmarks)
    frame: int = 0               # indice do frame onde apareceu (0 para imagem)


@dataclass
class PoseAnalysisResult:
    """Resultado da analise de POSE/atividade de um video/imagem (MediaPipe)."""
    sinais: list[DeteccaoPose] = field(default_factory=list)
    frames_analisados: int = 0   # quantos frames foram efetivamente processados
    backend: str = "local"       # qual adapter produziu (ex.: "local_mediapipe")


@dataclass
class DeteccaoEmocao:
    """
    Emocao facial dominante detectada num frame via DeepFace.

    NAO e diagnostico: e a emocao aparente do rosto naquele instante. Emocoes
    negativas sustentadas (tristeza/medo/raiva) viram indicio para a equipe.
    """
    emocao: str                  # ex.: "sad", "fear", "angry", "happy", "neutral"
    score: float                 # 0.0 .. 1.0 (confianca da emocao dominante)
    frame: int = 0               # indice do frame onde apareceu (0 para imagem)


@dataclass
class EmotionAnalysisResult:
    """Resultado da analise de EMOCAO facial de um video/imagem (DeepFace)."""
    emocoes: list[DeteccaoEmocao] = field(default_factory=list)
    frames_analisados: int = 0   # quantos frames foram efetivamente processados
    backend: str = "local"       # qual adapter produziu (ex.: "local_deepface")


@dataclass
class OcrResult:
    """Resultado da extracao de texto de um documento (PDF de laudo)."""
    texto: str
    paginas: int = 0             # quantas paginas foram processadas
    backend: str = "local"       # ex.: "pdfplumber", "pymupdf", "pytesseract"
    usou_ocr: bool = False       # True se precisou de OCR (PDF imagem/escaneado)


# ---------------------------------------------------------------------------
# Ports (interfaces abstratas)
# ---------------------------------------------------------------------------
class StoragePort(ABC):
    """Armazenamento de arquivos (uploads, resultados)."""

    @abstractmethod
    def salvar(self, nome: str, conteudo: bytes) -> str:
        """Persiste os bytes e devolve uma referencia (caminho local ou URI s3://)."""

    @abstractmethod
    def ler(self, referencia: str) -> bytes:
        """Recupera os bytes a partir da referencia devolvida por salvar()."""


class TranscriptionPort(ABC):
    """Transcricao de audio (fala -> texto)."""

    @abstractmethod
    def transcrever(self, caminho_wav: str, idioma: str = "pt-BR") -> TranscriptionResult:
        """Recebe o caminho de um arquivo WAV e devolve o texto transcrito."""


class NlpPort(ABC):
    """Processamento de linguagem natural (sentimento + entidades)."""

    @abstractmethod
    def analisar(self, texto: str) -> NlpResult:
        """Analisa o texto e devolve sentimento + entidades."""


class VideoPort(ABC):
    """Analise de video/imagem (deteccao de objetos)."""

    @abstractmethod
    def analisar(
        self,
        caminho: str,
        classes_foco: list[str],
        amostragem: int = 15,
        conf: float = 0.25,
    ) -> VideoAnalysisResult:
        """
        Detecta objetos em um arquivo de imagem ou video.

        - caminho: arquivo local (imagem .jpg/.png ou video .mp4/.avi/...).
        - classes_foco: classes que nos interessam (a deteccao traz todas, mas
          essas sao as monitoradas pelas regras de risco). Passada adiante para
          documentacao/contexto no resultado.
        - amostragem: em videos, processa 1 frame a cada N (reduz custo).
        - conf: confianca minima para considerar uma deteccao.
        """


class PosePort(ABC):
    """Analise de POSE/atividade corporal em video/imagem (MediaPipe)."""

    @abstractmethod
    def analisar(self, caminho: str, amostragem: int = 15) -> PoseAnalysisResult:
        """
        Detecta sinais corporais (postura/gesto) em uma imagem ou video.

        - caminho: arquivo local (imagem ou video).
        - amostragem: em videos, processa 1 frame a cada N (reduz custo).
        """


class EmotionPort(ABC):
    """Analise de EMOCAO facial em video/imagem (DeepFace)."""

    @abstractmethod
    def analisar(self, caminho: str, amostragem: int = 15) -> EmotionAnalysisResult:
        """
        Detecta a emocao facial dominante em uma imagem ou video.

        - caminho: arquivo local (imagem ou video).
        - amostragem: em videos, processa 1 frame a cada N (reduz custo).
        """


class OcrPort(ABC):
    """Extracao de texto de documentos (PDF de laudo). NUNCA usa Textract."""

    @abstractmethod
    def extrair_texto(self, caminho_pdf: str) -> OcrResult:
        """Recebe o caminho de um PDF e devolve o texto extraido."""


class SummarizerPort(ABC):
    """Sumarizacao de texto (resumo do laudo)."""

    @abstractmethod
    def resumir(self, texto: str) -> str:
        """Recebe um texto longo e devolve um resumo curto."""
