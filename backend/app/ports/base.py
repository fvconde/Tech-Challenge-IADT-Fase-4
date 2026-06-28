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
