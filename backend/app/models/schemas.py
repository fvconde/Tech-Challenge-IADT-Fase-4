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


class AchadoSchema(BaseModel):
    """Um indicio de risco localizado num trecho especifico de uma fonte."""

    fonte: str = Field(description="texto | audio | laudo | video | pose | emocao")
    trecho: str = Field(description="Conteudo (frase) que motivou o indicio.")
    categoria: str = Field(description="Categoria de risco detectada nesse trecho.")
    score: float = Field(description="0.0 a 1.0 - intensidade dos indicios no trecho.")
    metadados: dict = Field(
        default_factory=dict,
        description="Posicao/contexto do trecho (ex.: indice_trecho, frame).",
    )


class DeteccaoVisualSchema(BaseModel):
    classe: str = Field(description="Classe COCO detectada (ex.: knife, scissors, person)")
    confianca: float = Field(description="0.0 a 1.0")
    frame: int = Field(description="Indice do frame (0 para imagem)")


class DeteccaoPoseSchema(BaseModel):
    sinal: str = Field(
        description="Sinal corporal detectado (ex.: maos_proximas_ao_rosto). "
        "NAO e diagnostico, apenas indicio observavel."
    )
    confianca: float = Field(description="0.0 a 1.0")
    frame: int = Field(description="Indice do frame (0 para imagem)")


class DeteccaoEmocaoSchema(BaseModel):
    emocao: str = Field(description="Emocao facial aparente (ex.: sad, fear, happy)")
    score: float = Field(description="0.0 a 1.0 - confianca da emocao dominante")
    frame: int = Field(description="Indice do frame (0 para imagem)")


# ------- Anotacao de emocao em VIDEO (grafico hexagono + video anotado) -------
class EmocaoPerfilSchema(BaseModel):
    """Um eixo do hexagono: intensidade media de uma emocao no video (0..1)."""

    emocao: str = Field(description="Rótulo PT da emoção (eixo do hexágono)")
    valor: float = Field(description="0.0 a 1.0 - intensidade média nos frames com rosto")
    negativa: bool = Field(description="True para emoções de valência negativa")


class EmocaoFrameSchema(BaseModel):
    """Emocao dominante de um frame amostrado (para a faixa/timeline)."""

    frame: int = Field(description="Índice do frame amostrado")
    tempo_s: float = Field(description="Instante aproximado no vídeo (segundos)")
    emocao: str = Field(description="Rótulo PT da emoção dominante do frame")
    score: float = Field(description="0.0 a 1.0 - confiança da emoção dominante")


class EmocaoVideoPanel(BaseModel):
    """Painel de emoção do vídeo: perfil (hexágono) + timeline + URL do vídeo anotado.

    Embutido em ``AnaliseRiscoResponse.emocao_video`` quando EMOTION_BACKEND=local
    e o arquivo analisado é um vídeo (gerado na MESMA passada do DeepFace que
    produz a categoria de risco 'sinal_emocional_negativo').
    """

    video_id: str
    video_url: str = Field(
        description="Caminho relativo para baixar/reproduzir o vídeo anotado (MP4/H.264)."
    )
    perfil: list[EmocaoPerfilSchema] = Field(default_factory=list)
    timeline: list[EmocaoFrameSchema] = Field(default_factory=list)
    frames_analisados: int = Field(description="Frames em que o DeepFace rodou (amostrados)")
    frames_total: int = Field(description="Total de frames escritos no vídeo anotado")
    frames_com_rosto: int = Field(description="Frames amostrados em que houve rosto")
    fps: float
    dominante_geral: str = Field(description="Emoção dominante no vídeo inteiro (PT)")
    backend: str = "local_deepface"


# --------------------------- Response ---------------------------
class AnaliseRiscoResponse(BaseModel):
    """Resposta unificada de analise (texto, audio, video ou multimodal)."""

    transcricao: str | None = Field(
        default=None,
        description="Texto transcrito (apenas quando ha audio).",
    )
    categorias_risco: list[CategoriaRiscoSchema] = Field(default_factory=list)
    achados: list[AchadoSchema] = Field(
        default_factory=list,
        description="Categorização por trecho (chunk), com rastreabilidade de fonte e posição.",
    )
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
    # detalhes de pose (apenas quando a analise de pose roda - POSE_BACKEND=local)
    deteccoes_pose: list[DeteccaoPoseSchema] | None = None
    # detalhes de emocao (apenas quando a analise de emocao roda - EMOTION_BACKEND=local)
    deteccoes_emocao: list[DeteccaoEmocaoSchema] | None = None
    # painel de emocao (hexagono + video anotado): so quando ha VIDEO + EMOTION_BACKEND=local
    emocao_video: EmocaoVideoPanel | None = None
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
    backend_pose: str | None = None
    backend_emocao: str | None = None
    backend_ocr: str | None = None
    backend_summarizer: str | None = None
