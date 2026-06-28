"""
Testes da analise de risco em texto (100% offline, sem nuvem nem internet).
"""

from __future__ import annotations

from backend.app.models.schemas import NivelAlerta
from backend.app.ports.nlp import LocalNlpAdapter
from backend.app.services.text.nlp import analisar_texto

nlp = LocalNlpAdapter()


def test_violencia_domestica_gera_alerta_alto():
    texto = (
        "Eu tenho medo dele em casa. Ele me empurrou e me ameacou, "
        "ele me controla e eu nao posso sair de casa."
    )
    r = analisar_texto(texto, nlp)
    categorias = {c.categoria for c in r.categorias_risco}
    assert "violencia_domestica" in categorias
    assert r.nivel_alerta == NivelAlerta.alto
    # alerta deve trazer evidencias (rastreabilidade)
    viol = next(c for c in r.categorias_risco if c.categoria == "violencia_domestica")
    assert len(viol.evidencias) >= 1


def test_depressao_pos_parto_detectada():
    texto = (
        "Desde que o bebe nasceu eu choro o dia todo e me sinto um fracasso, "
        "estou exausta e triste."
    )
    r = analisar_texto(texto, nlp)
    categorias = {c.categoria for c in r.categorias_risco}
    assert "depressao_pos_parto" in categorias
    assert r.sentimento.rotulo == "negativo"
    assert r.nivel_alerta in (NivelAlerta.medio, NivelAlerta.alto)


def test_consulta_rotina_sem_risco():
    texto = "Vim para a consulta de rotina, estou bem e tranquila, apoiada pela familia."
    r = analisar_texto(texto, nlp)
    assert r.categorias_risco == []
    assert r.nivel_alerta == NivelAlerta.baixo


def test_resposta_sempre_tem_aviso_etico():
    r = analisar_texto("texto qualquer", nlp)
    assert "NAO e diagnostico" in r.aviso
