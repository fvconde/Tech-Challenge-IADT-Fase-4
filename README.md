# Tech Challenge Fase 4 — IA Multimodal para Saúde e Segurança da Mulher

Solução de **apoio à decisão clínica** que processa **áudio, vídeo e texto** de
consultas para identificar **precocemente sinais de risco** (saúde materna/ginecológica,
violência doméstica, bem-estar psicológico).

> ⚠️ **Postura ética:** o sistema **gera alertas para a equipe especializada**.
> Ele **NÃO emite diagnóstico automático**. Toda saída é apoio à decisão humana.

> 🔒 **LGPD:** este repositório **não contém PHI** (dados reais de pacientes).
> Apenas material **sintético** em `data/samples/`.

---

## Visão da arquitetura

O sistema roda **100% local por padrão** (custo zero, sem credenciais de nuvem).
A nuvem (AWS) é **opcional** e entra só via *adapters*, escolhidos por variável de
ambiente. Inspirado em injeção de dependência: **uma interface (port), duas
implementações (local default | cloud opcional)**.

```
                +------------------- FastAPI (REST) -------------------+
   upload --->  | /api/text   /api/audio   /api/video   /api/fusion    |
                +------------------------------------------------------+
                                |            |             |
                          services/text  services/audio  services/video
                                |            |             |
                +---------------v------------v-------------v-----------+
                |                   PORTS (interfaces)                  |
                |  StoragePort   NlpPort   TranscriptionPort  ...       |
                +------+----------------+-----------------+------------+
                       |                |                 |
                  LocalStorage     LocalNlp          RecognizeGoogle   <- default (local)
                  S3Storage        Comprehend        (mock)            <- opcional/cloud
```

Detalhes e justificativas em [docs/decisoes-arquiteturais.md](docs/decisoes-arquiteturais.md).

---

## Pré-requisitos

- **Python 3.11+** (esta máquina usa 3.12 — compatível).
- (Opcional) `ffmpeg` no PATH — só se for converter áudio mp3/m4a. WAV funciona sem ele.

---

## Setup rápido (Windows / PowerShell)

```powershell
# 1) criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) instalar dependencias core (audio + nlp + api)
pip install -r requirements.txt

# 3) configurar variaveis de ambiente
Copy-Item .env.example .env       # ajuste se quiser; o default ja roda 100% local

# 4) subir a API
uvicorn backend.app.main:app --reload
```

Setup equivalente em Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload
```

A API sobe em `http://127.0.0.1:8000`. Documentação interativa em
`http://127.0.0.1:8000/docs`.

---

## Fatia vertical entregue (Sessão 1): análise de áudio/texto

Pipeline ponta-a-ponta **sem nuvem**:

1. `POST /api/audio/analyze` — recebe um **WAV** de consulta → transcreve
   (`recognize_google`) → analisa risco na fala → devolve **alerta estruturado**.
2. `POST /api/text/analyze` — recebe **texto** (ex.: relato/transcrição) → mesma
   análise de risco. Útil para testar offline (sem internet/áudio).

Exemplo (texto, roda offline):

```powershell
$body = @{ texto = "Nao consigo dormir, choro o dia todo desde que o bebe nasceu e me sinto um fracasso." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/text/analyze -Method Post -Body $body -ContentType "application/json"
```

Resposta (resumida):

```json
{
  "categorias_risco": [{"categoria": "depressao_pos_parto", "score": 0.8, "evidencias": ["choro o dia todo", "fracasso"]}],
  "sentimento": {"rotulo": "negativo", "score": -0.6},
  "nivel_alerta": "alto",
  "acao_recomendada": "Encaminhar para avaliacao da equipe especializada (saude mental perinatal).",
  "aviso": "Apoio a decisao. NAO e diagnostico."
}
```

---

## Vídeo (YOLOv8) e fusão multimodal

O vídeo agora está **integrado ao backend** (não só no notebook). YOLOv8n pré-treinado,
local, com a "customização" nas **regras de risco** (classes-foco configuráveis).

```powershell
pip install ultralytics opencv-python    # já no requirements (puxa torch ~ centenas de MB)

# 1) gerar um vídeo sintético de exemplo (sem PHI)
python scripts/gerar_video_exemplo.py

# 2) analisar só o vídeo
curl.exe -F "arquivo=@data/samples/video_exemplo.mp4" http://127.0.0.1:8000/api/video/analyze

# 3) FUSÃO multimodal: texto + vídeo num alerta único
curl.exe -F "texto=tenho medo dele, ele me empurrou" -F "video_arquivo=@data/samples/video_exemplo.mp4" http://127.0.0.1:8000/api/fusion/analyze
```

A detecção usa classes COCO genéricas; as **regras de risco** (`VIDEO_FOCUS_CLASSES`,
default `knife,scissors`) decidem o que vira `objeto_suspeito_automutilacao`. Para um
demo de alerta **alto** com modelo real, use um clipe/imagem contendo faca ou tesoura.
O notebook [notebooks/01_yolov8_demo.ipynb](notebooks/01_yolov8_demo.ipynb) segue
disponível para inspeção visual da detecção.

> A resposta de `/api/video/analyze` (e da fusão) inclui **`imagem_anotada_b64`**: a imagem
> com as bounding boxes desenhadas pelo YOLOv8 (JPEG em base64), pronta para exibir no
> frontend. Para vídeos, é anotado o frame de maior confiança.

---

## Laudos (PDF): OCR + sumarização

Extração de texto de PDF **100% local** (pdfplumber → PyMuPDF → pytesseract), **sem
Textract**. O laudo entra na mesma fusão como modalidade `laudo`.

```powershell
# 1) gerar um PDF de laudo sintetico (sem PHI)
python scripts/gerar_laudo_exemplo.py

# 2) analisar o laudo (extrai texto -> risco -> resumo)
curl.exe -F "arquivo=@data/samples/laudo_exemplo.pdf" http://127.0.0.1:8000/api/laudo/analyze

# 3) FUSAO com 3 modalidades: texto + video + laudo
curl.exe -F "texto=tenho medo dele" -F "video_arquivo=@data/samples/video_exemplo.mp4" -F "laudo_arquivo=@data/samples/laudo_exemplo.pdf" http://127.0.0.1:8000/api/fusion/analyze
```

**Sumarização:** default `distilbart-cnn` (`SUMMARIZER_BACKEND=distilbart`, baixa ~1GB na
1ª vez). Para não baixar nada, use `SUMMARIZER_BACKEND=extractive`. Avaliação ROUGE:

```powershell
python scripts/avaliar_rouge.py     # ROUGE-1/2/L do resumo vs. referência sintética
```

---

## Nuvem AWS (opcional, de-risco da demo)

Os adapters de nuvem (`S3StorageAdapter`, `ComprehendAdapter`) são **opcionais**; o default
é local. Para confirmar se sua conta AWS permite os serviços **antes da demo**, há um smoke
**opt-in** (não roda no pytest):

```powershell
# configure credenciais e bucket no .env (NUNCA commitar):
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME
$env:RUN_AWS_SMOKE=1
python scripts/smoke_aws.py     # sobe o laudo no S3 + 1 chamada ao Comprehend
```

> ⚠️ **Conformidade:** o Comprehend **envia o texto a um terceiro (AWS)** e consome crédito.
> Use **apenas o laudo sintético**, poucas chamadas. Default permanece local/offline.

---

## Frontend (Angular 19)

Interface web que consome a API e demonstra o fluxo multimodal ponta-a-ponta — **página
única** com sidebar fixa (entradas por modalidade) e feed de resultados. Destaques de
apresentação: **badge de severidade** (verde/âmbar/vermelho), **spinner** por botão
enquanto a requisição roda, **botões de exemplo** (pós-parto / violência / rotina), exibição
da **imagem anotada** do YOLOv8 e o **alerta à equipe médica** na fusão.

```powershell
# com o backend rodando (uvicorn) em http://127.0.0.1:8000:
npm --prefix frontend install    # 1ª vez
npm --prefix frontend start      # abre http://localhost:4200
```

O backend libera **CORS** para `http://localhost:4200`. Detalhes em
[frontend/README.md](frontend/README.md).

---

## Testes

```powershell
pip install pytest
pytest backend/tests -q
```

---

## Estrutura

Ver seção 7 do [CLAUDE.md](CLAUDE.md). Resumo:

- `backend/app/ports/` — interfaces + adapters local/cloud (storage, nlp, transcription,
  video, ocr, summarizer)
- `backend/app/services/` — lógica por modalidade (audio, text/document, video, fusion)
- `backend/app/api/routers/` — endpoints REST (text, audio, video, laudo, fusion)
- `scripts/` — geradores de exemplo (vídeo, laudo), ROUGE e smoke AWS
- `frontend/` — app Angular 19 (interface web da demo)
- `notebooks/` — demos (YOLOv8, NLP)
- `data/samples/` — dados sintéticos (sem PHI)
- `docs/` — relatório técnico e decisões arquiteturais

---

## Roadmap (próximas sessões)

- [x] Vídeo: YOLOv8 integrado ao backend (`/api/video/analyze`) via `VideoPort`
- [x] Fusão multimodal (texto + vídeo + laudo → alerta único) em `/api/fusion/analyze`
- [x] OCR local de laudos (pdfplumber/PyMuPDF/pytesseract) — substituto do Textract
- [x] Sumarização local (transformers `distilbart`) + avaliação ROUGE
- [x] Adapters de nuvem (S3 + Comprehend) com smoke opt-in (`scripts/smoke_aws.py`)
- [x] Frontend Angular 19 (interface multimodal + alerta à equipe)
- [ ] Vídeo: somar DeepFace (emoção) + MediaPipe (pose) na mesma fusão
- [ ] Bedrock (sumarização/agente) na demo final, se sobrar crédito
- [ ] Gravar o vídeo de demonstração (até 15 min)
