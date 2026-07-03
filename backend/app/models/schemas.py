"""
Schemas Pydantic = contrato de entrada/saida da API REST.

Separados dos dataclasses do dominio (ports/base.py) de proposito:
- ports/base.py  -> tipos internos, sem dependencia de framework.
- models/schemas.py -> o que entra e sai pela API (validacao + documentacao /docs).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# Aviso etico padrao anexado a TODA resposta de analise.
AVISO_PADRAO = (
    "Apoio à decisão clínica. NÃO é diagnóstico. "
    "Resultado deve ser avaliado pela equipe especializada."
)


class NivelAlerta(str, Enum):
    baixo = "baixo"
    medio = "medio"
    alto = "alto"


# --------------------------- Requests ---------------------------
class TextoRequest(BaseModel):
    texto: str = Field(
        ...,
        min_length=1,
        description="Texto a analisar (relato, transcricao de consulta, etc.).",
        examples=["Nao consigo dormir e choro o dia todo desde que o bebe nasceu."],
    )


# --------------------------- Sub-objetos ---------------------------
class SentimentoSchema(BaseModel):
    rotulo: str = Field(description="positivo | neutro | negativo")
    score: float = Field(description="-1.0 (muito negativo) a +1.0 (muito positivo)")
    backend: str = "local"


class EntidadeSchema(BaseModel):
    texto: str
    tipo: str = Field(description="sintoma | medicamento | tempo | ...")


class CategoriaRiscoSchema(BaseModel):
    categoria: str = Field(
        description="ex.: depressao_pos_parto | ansiedade | violencia_domestica | "
        "fadiga_hormonal | objeto_suspeito_automutilacao"
    )
    score: float = Field(description="0.0 a 1.0 - intensidade dos indicios encontrados")
    evidencias: list[str] = Field(
        default_factory=list,
        description="Trechos/termos/deteccoes que motivaram o indicio (rastreabilidade).",
    )


class DeteccaoVisualSchema(BaseModel):
    classe: str = Field(description="Classe COCO detectada (ex.: knife, scissors, person)")
    confianca: float = Field(description="0.0 a 1.0")
    frame: int = Field(description="Indice do frame (0 para imagem)")


# --------------------------- Response ---------------------------
class AnaliseRiscoResponse(BaseModel):
    """Resposta unificada de analise (texto, audio, video ou multimodal)."""

    transcricao: str | None = Field(
        default=None,
        description="Texto transcrito (apenas quando ha audio).",
    )
    categorias_risco: list[CategoriaRiscoSchema] = Field(default_factory=list)
    sentimento: SentimentoSchema
    entidades: list[EntidadeSchema] = Field(default_factory=list)
    nivel_alerta: NivelAlerta
    acao_recomendada: str
    aviso: str = AVISO_PADRAO
    # quais modalidades contribuiram para este alerta (ex.: ["texto", "video"])
    modalidades: list[str] = Field(default_factory=list)
    # detalhes de video (apenas quando ha video)
    deteccoes_video: list[DeteccaoVisualSchema] | None = None
    frames_analisados: int | None = None
    imagem_anotada_b64: str | None = Field(
        default=None,
        description="Imagem com bounding boxes do YOLOv8 (JPEG em base64), quando ha video/imagem.",
    )
    # detalhes de laudo/documento (apenas quando ha PDF)
    texto_documento: str | None = Field(
        default=None, description="Texto extraido do PDF de laudo."
    )
    resumo: str | None = Field(
        default=None, description="Resumo do laudo (sumarizacao)."
    )
    # rastreabilidade de backends usados
    backend_transcricao: str | None = None
    backend_nlp: str | None = None
    backend_video: str | None = None
    backend_ocr: str | None = None
    backend_summarizer: str | None = None
