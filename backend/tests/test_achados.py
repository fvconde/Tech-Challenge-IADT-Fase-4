"""
Testes da categorizacao por TRECHO (achados), complementar ao agregado por
categoria. 100% offline (mesmo lexico usado pelo agregado).
"""

from __future__ import annotations

from backend.app.ports.nlp import LocalNlpAdapter
from backend.app.services.audio.pipeline import analisar_audio
from backend.app.services.text.achados import detectar_achados, segmentar
from backend.app.services.text.document import analisar_laudo
from backend.app.services.text.nlp import analisar_texto
from backend.app.ports.ocr import MockOcrAdapter
from backend.app.ports.summarizer import ExtractiveSummarizerAdapter

nlp = LocalNlpAdapter()


# --------------------------- segmentar ---------------------------
def test_segmentar_quebra_por_pontuacao_e_ignora_vazios():
    texto = "Estou ansiosa. Ele me ameacou! \n\n Tudo bem por aqui."
    trechos = segmentar(texto)
    assert trechos == ["Estou ansiosa", "Ele me ameacou", "Tudo bem por aqui"]


def test_segmentar_texto_vazio_devolve_lista_vazia():
    assert segmentar("") == []
    assert segmentar("   ") == []


# --------------------------- detectar_achados ---------------------------
def test_detectar_achados_duas_frases_categorias_diferentes():
    texto = "Estou muito ansiosa e com o coracao acelerado. Ele me ameacou varias vezes."
    achados = detectar_achados(texto, fonte="texto")

    categorias = {a.categoria for a in achados}
    assert "ansiedade" in categorias
    assert "violencia_domestica" in categorias

    ansiedade = next(a for a in achados if a.categoria == "ansiedade")
    violencia = next(a for a in achados if a.categoria == "violencia_domestica")

    assert ansiedade.fonte == "texto"
    assert "ansiosa" in ansiedade.trecho.lower()
    assert violencia.trecho != ansiedade.trecho
    assert ansiedade.metadados["indice_trecho"] < violencia.metadados["indice_trecho"]


def test_detectar_achados_sem_gatilho_devolve_lista_vazia():
    texto = "Vim para a consulta de rotina, estou bem e tranquila."
    assert detectar_achados(texto, fonte="texto") == []


def test_detectar_achados_texto_vazio_devolve_lista_vazia():
    assert detectar_achados("", fonte="texto") == []


# --------------------------- integracao por modalidade ---------------------------
def test_analisar_texto_expoe_achados_com_fonte_texto():
    texto = "Ele me bateu e eu tenho medo dele em casa."
    r = analisar_texto(texto, nlp)
    assert len(r.achados) >= 1
    assert all(a.fonte == "texto" for a in r.achados)
    assert any(a.categoria == "violencia_domestica" for a in r.achados)


def test_analisar_audio_expoe_achados_com_fonte_audio():
    from backend.app.ports.transcription import MockTranscriptionAdapter

    # analisar_audio grava um arquivo temporario proprio (nome aleatorio), entao
    # usamos texto_padrao em vez de um .txt irmao (que nunca seria encontrado).
    transcription = MockTranscriptionAdapter(
        texto_padrao="Estou exausta e triste, sem vontade de nada."
    )
    r = analisar_audio(
        nome_arquivo="consulta.wav",
        conteudo=b"RIFF....WAVEfmt ",
        transcription=transcription,
        nlp=nlp,
    )
    assert len(r.achados) >= 1
    assert all(a.fonte == "audio" for a in r.achados)
    assert any(a.categoria == "depressao_pos_parto" for a in r.achados)


def test_analisar_laudo_expoe_achados_com_fonte_laudo():
    ocr = MockOcrAdapter(
        texto_padrao="A paciente chora o dia todo e se sente um fracasso, com insonia."
    )
    summarizer = ExtractiveSummarizerAdapter()
    resultado = analisar_laudo(
        nome_arquivo="laudo.pdf",
        conteudo=b"%PDF-1.4 conteudo fake",
        ocr=ocr,
        nlp=nlp,
        summarizer=summarizer,
    )
    assert len(resultado.achados) >= 1
    assert all(a.fonte == "laudo" for a in resultado.achados)
    assert any(a.categoria == "depressao_pos_parto" for a in resultado.achados)
