"""
Testes da FUSAO multimodal: a combinacao de categorias e o endpoint /api/fusion/analyze.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.schemas import NivelAlerta
from backend.app.ports.base import (
    DeteccaoCategoria,
    DeteccaoVisual,
    SentimentResult,
    TranscriptionResult,
)
from backend.app.ports.emotion import MockEmotionAdapter
from backend.app.ports.factory import (
    get_emotion,
    get_pose,
    get_storage,
    get_transcription,
    get_video,
)
from backend.app.ports.pose import MockPoseAdapter
from backend.app.ports.video import MockVideoAdapter
from backend.app.services.fusion.alerts import (
    ACAO_POR_CATEGORIA,
    BOOST_CORROBORACAO,
    avaliar_alerta,
    combinar_categorias,
)
from backend.app.services.fusion.multimodal import fundir

_SENT_NEG = SentimentResult(rotulo="negativo", score=-0.6, backend="local")

client = TestClient(app)


# --------------------- combinar_categorias (unidade) ---------------------
def test_combinar_categorias_corroboracao_multimodal():
    # mesma categoria vista por duas modalidades -> boost + uniao de evidencias
    texto = [DeteccaoCategoria("ansiedade", 0.6, ["texto: ansiosa"])]
    video = [DeteccaoCategoria("ansiedade", 0.5, ["video: sinal X"])]
    comb = combinar_categorias(texto, video)

    assert len(comb) == 1
    c = comb[0]
    assert c.score == round(min(1.0, 0.6 + BOOST_CORROBORACAO), 3)
    assert any("corroboração" in e for e in c.evidencias)
    assert "texto: ansiosa" in c.evidencias and "video: sinal X" in c.evidencias


def test_combinar_categorias_uniao_simples():
    texto = [DeteccaoCategoria("violencia_domestica", 0.9, ["a"])]
    video = [DeteccaoCategoria("objeto_suspeito_automutilacao", 0.8, ["b"])]
    comb = combinar_categorias(texto, video)
    cats = {c.categoria for c in comb}
    assert cats == {"violencia_domestica", "objeto_suspeito_automutilacao"}


# --------------------- contador de corroboracao (item 1) ---------------------
def test_fundir_lista_todas_modalidades_com_pose_e_emocao():
    # Regressao do contador do card ("X/3 canais"): com pose+emocao (e audio) ativos,
    # 'modalidades' deve listar TODAS as modalidades presentes -> o numerador do card
    # (modalidades.length) e o total real, nunca uma fracao incoerente sobre 3.
    resp = fundir(
        categorias_texto=[DeteccaoCategoria("depressao_pos_parto", 1.0, ["x"])],
        categorias_audio=[DeteccaoCategoria("ansiedade", 0.6, ["a"])],
        categorias_video=[DeteccaoCategoria("objeto_suspeito_automutilacao", 0.5, ["v"])],
        categorias_pose=[DeteccaoCategoria("sinal_corporal_estresse", 0.9, ["p"])],
        categorias_emocao=[DeteccaoCategoria("sinal_emocional_negativo", 0.9, ["e"])],
    )
    assert "pose" in resp.modalidades
    assert "emocao" in resp.modalidades
    assert set(resp.modalidades) == {"texto", "audio", "video", "pose", "emocao"}
    # 5 modalidades -> o card mostra "5 canais" (antes: "5/3", incoerente)
    assert len(resp.modalidades) == 5


# --------------------- priorizacao da acao (item 2) ---------------------
def test_acao_nao_dominada_por_critica_fraca():
    # Caso exato: pos-parto FORTE (texto+laudo, corroborado) + video com sinal critico
    # FRACO (objeto_suspeito 0.33, 1 modalidade). A acao NAO deve ser dominada pelo fraco.
    texto = [
        DeteccaoCategoria("depressao_pos_parto", 1.0, ["nao paro de chorar", "fracasso"]),
        DeteccaoCategoria("ansiedade", 1.0, ["insonia"]),
    ]
    laudo = [
        DeteccaoCategoria("depressao_pos_parto", 0.9, ["fracasso"]),
        DeteccaoCategoria("ansiedade", 0.8, ["ansiedade"]),
    ]
    video = [DeteccaoCategoria("objeto_suspeito_automutilacao", 0.33, ["scissors (conf 0.33, frame 0)"])]

    combinadas = combinar_categorias(texto, laudo, video)
    nivel, acao = avaliar_alerta(combinadas, _SENT_NEG)

    # nivel segue ALTO (critica presente -> seguranca; regra inalterada)
    assert nivel == NivelAlerta.alto
    # a acao LIDERA com o cuidado de pos-parto (sinal forte corroborado)...
    assert ACAO_POR_CATEGORIA["depressao_pos_parto"] in acao
    # ...e trata a critica fraca como VERIFICACAO, nao como comando prioritario isolado
    assert "verificação" in acao
    assert acao != ACAO_POR_CATEGORIA["objeto_suspeito_automutilacao"]


def test_critica_forte_mantem_acao_prioritaria():
    # Regressao: objeto_suspeito REAL forte (0.85) NAO e rebaixado -> preserva a demo (§6).
    texto = [DeteccaoCategoria("depressao_pos_parto", 1.0, ["fracasso"])]
    laudo = [DeteccaoCategoria("depressao_pos_parto", 0.9, ["fracasso"])]
    video = [DeteccaoCategoria("objeto_suspeito_automutilacao", 0.85, ["scissors (conf 0.85, frame 0)"])]

    combinadas = combinar_categorias(texto, laudo, video)
    nivel, acao = avaliar_alerta(combinadas, _SENT_NEG)

    assert nivel == NivelAlerta.alto
    # critica forte continua sendo o comando prioritario (sem rebaixamento)
    assert acao == ACAO_POR_CATEGORIA["objeto_suspeito_automutilacao"]


# --------------------- endpoint /api/fusion/analyze ---------------------
def test_fusion_texto_mais_video():
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("knife", 0.8, 3)]
    )
    try:
        r = client.post(
            "/api/fusion/analyze",
            data={"texto": "tenho medo dele, ele me empurrou e me ameacou em casa"},
            files={"video_arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert set(b["modalidades"]) == {"texto", "video"}
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "violencia_domestica" in cats
    assert "objeto_suspeito_automutilacao" in cats
    assert b["nivel_alerta"] == "alto"
    assert b["deteccoes_video"] is not None


def test_fusion_imagem_gera_categoria_e_repassa_anotada():
    # regressao: quando o video/imagem detecta uma classe-foco, a FUSAO deve
    # (1) gerar a categoria de risco visual e (2) repassar a imagem anotada no
    # response (o card da fusao exibe a mesma imagem do card isolado).
    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("scissors", 0.85, 0)],
        imagem_anotada_b64="ZmFrZQ==",  # "fake" em base64
    )
    try:
        r = client.post(
            "/api/fusion/analyze",
            data={"texto": "vim para a consulta de rotina, estou tranquila"},
            files={"video_arquivo": ("foto.jpg", b"fake-img", "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert set(b["modalidades"]) == {"texto", "video"}
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "objeto_suspeito_automutilacao" in cats
    assert b["nivel_alerta"] == "alto"  # categoria critica -> alto
    assert b["imagem_anotada_b64"] == "ZmFrZQ=="  # anotada presente na fusao


def test_fusion_combina_audio_e_dois_visuais_sem_descartar_imagem():
    # A fusao agora USA o audio e COMBINA video + imagem (imagem nao e descartada).
    class _StubTranscription:
        def transcrever(self, caminho, idioma="pt-BR"):
            return TranscriptionResult(
                texto="tenho medo dele ele me empurrou", idioma=idioma, backend="stub"
            )

    class _StubStorage:  # evita tocar no S3/rede durante o teste
        def salvar(self, nome, conteudo):
            return f"stub://{nome}"

        def ler(self, referencia):
            return b""

    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("scissors", 0.85, 0)], imagem_anotada_b64="ZmFrZQ=="
    )
    app.dependency_overrides[get_pose] = lambda: MockPoseAdapter()
    app.dependency_overrides[get_emotion] = lambda: MockEmotionAdapter()
    app.dependency_overrides[get_transcription] = lambda: _StubTranscription()
    app.dependency_overrides[get_storage] = lambda: _StubStorage()
    try:
        r = client.post(
            "/api/fusion/analyze",
            data={"texto": "consulta de rotina, tranquila"},
            files={
                "audio_arquivo": ("fala.wav", b"fake-wav", "audio/wav"),
                "video_arquivo": ("clip.mp4", b"fake-video", "video/mp4"),
                "imagem_arquivo": ("tesoura.jpg", b"fake-img", "image/jpeg"),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    # audio entrou como modalidade; video presente (video+imagem = 1 canal visual)
    assert "audio" in b["modalidades"]
    assert "video" in b["modalidades"]
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "violencia_domestica" in cats            # veio do audio transcrito
    assert "objeto_suspeito_automutilacao" in cats  # veio do(s) visual(is)
    assert b["nivel_alerta"] == "alto"
    # imagem NAO descartada: os DOIS visuais foram processados -> 2 deteccoes
    assert len(b["deteccoes_video"]) == 2
    assert b["transcricao"] == "tenho medo dele ele me empurrou"


def test_fusion_audio_invalido_nao_derruba_a_fusao():
    # Robustez: um audio ilegivel (ex.: MP3 renomeado p/ .wav) NAO pode derrubar a
    # fusao com 500 -> a modalidade audio fica ausente e o resto segue.
    class _RaisingTranscription:
        def transcrever(self, caminho, idioma="pt-BR"):
            raise ValueError("audio nao e um WAV/FLAC valido")

    class _StubStorage:
        def salvar(self, nome, conteudo):
            return f"stub://{nome}"

        def ler(self, referencia):
            return b""

    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(
        deteccoes=[DeteccaoVisual("knife", 0.8, 0)]
    )
    app.dependency_overrides[get_pose] = lambda: MockPoseAdapter()
    app.dependency_overrides[get_emotion] = lambda: MockEmotionAdapter()
    app.dependency_overrides[get_transcription] = lambda: _RaisingTranscription()
    app.dependency_overrides[get_storage] = lambda: _StubStorage()
    try:
        r = client.post(
            "/api/fusion/analyze",
            files={
                "audio_arquivo": ("fala.wav", b"nao-e-wav", "audio/wav"),
                "video_arquivo": ("clip.mp4", b"fake-video", "video/mp4"),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200  # NAO derrubou
    b = r.json()
    assert "audio" not in b["modalidades"]  # audio falhou -> ausente
    assert "video" in b["modalidades"]      # o resto seguiu normal


def test_fusion_somente_texto():
    r = client.post(
        "/api/fusion/analyze",
        data={"texto": "estou bem e tranquila, consulta de rotina"},
    )
    assert r.status_code == 200
    b = r.json()
    assert b["modalidades"] == ["texto"]
    assert b["nivel_alerta"] == "baixo"


def test_fusion_exige_ao_menos_uma_modalidade():
    r = client.post("/api/fusion/analyze", data={})
    assert r.status_code == 400


def test_fusion_trilha_de_audio_do_video_flagra_risco(monkeypatch):
    # Regressao: a fusao chamava analisar_video SEM transcrever a trilha de audio do
    # video, entao um risco SO audivel na fala do video (sem deteccao visual) sumia na
    # fusao -- ficando MAIS FRACA que o /api/video/analyze isolado (que transcreve).
    # Aqui a trilha (mock) acusa violencia_domestica -> a fusao deve chegar em ALTO,
    # igual ao endpoint isolado, com a modalidade 'audio' presente.
    monkeypatch.setattr(
        "backend.app.services.video.pipeline.extrair_audio_de_video",
        lambda caminho_video: "fake.wav",
    )

    class _StubTranscription:
        def transcrever(self, caminho, idioma="pt-BR"):
            return TranscriptionResult(
                texto="tenho medo dele ele me empurrou e me ameacou",
                idioma=idioma,
                backend="stub",
            )

    app.dependency_overrides[get_video] = lambda: MockVideoAdapter(deteccoes=[])
    app.dependency_overrides[get_transcription] = lambda: _StubTranscription()
    try:
        r = client.post(
            "/api/fusion/analyze",
            files={"video_arquivo": ("clip.mp4", b"fake-video", "video/mp4")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert "audio" in b["modalidades"]
    cats = {c["categoria"] for c in b["categorias_risco"]}
    assert "violencia_domestica" in cats
    assert b["nivel_alerta"] == "alto"
    assert b["transcricao"] == "tenho medo dele ele me empurrou e me ameacou"
