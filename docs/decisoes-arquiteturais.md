# Decisões Arquiteturais

Este documento registra as decisões de projeto que precisam ser **justificadas e
documentadas** (exigência do brief e do CLAUDE.md), em especial as que tocam
**LGPD, custo e dependência de nuvem**.

---

## 1. Postura ética: apoio à decisão, nunca diagnóstico

O sistema **gera alertas para a equipe especializada** e **recomenda ações**.
Ele **não emite diagnóstico automático**. Toda resposta da API inclui o campo
`aviso` reforçando isso, e as ações são redigidas como "encaminhar / sinalizar /
acionar protocolo", nunca como conclusão clínica.

## 2. Custo de infraestrutura = ZERO (default 100% local)

- O sistema **sobe e roda sem nenhuma credencial de nuvem**. Todos os defaults
  (`STORAGE_BACKEND=local`, `NLP_BACKEND=local`, `TRANSCRIPTION_BACKEND=recognize_google`)
  apontam para implementações locais — exceto a transcrição (ver item 4).
- A nuvem é **opcional** e isolada atrás de *ports/adapters*. Trocar local↔cloud é
  mudar uma variável de ambiente; nenhum `boto3` é chamado direto dos routers.

### Realidade do Free Tier (conta nova, por créditos)
A conta AWS do autor é do **modelo novo (créditos US$100–200, ~12 meses)**, sem
trials de 12 meses por serviço. Logo, créditos são **orçamento escasso**:

| Serviço      | Decisão / resultado real                                          |
|--------------|------------------------------------------------------------------|
| **S3**       | ✅ **Funciona** (Always-Free). `S3StorageAdapter` disponível.     |
| **Comprehend** | ❌ **Indisponível** (`SubscriptionRequiredException`). → NLP local.|
| Rekognition  | Não usar (visão é local — YOLOv8/DeepFace/MediaPipe).            |
| Bedrock      | Não usado (sumarização é local via distilbart).                 |
| **Textract** | **Bloqueado / não usar.** OCR de laudos é 100% local.           |

> Resultado confirmado por smoke contra a conta real — ver **item 7**.
> Ação recomendada: criar um **AWS Budget de US$1** com alerta, desde já.

## 3. Padrão ports/adapters (injeção de dependência)

Para cada capacidade externa definimos uma **interface (port)** e implementações
**local (default)** e **cloud (opcional)**:

| Port              | Local (default)             | Cloud (opcional)     | Status na Sessão 1 |
|-------------------|-----------------------------|----------------------|--------------------|
| `StoragePort`     | `LocalStorageAdapter`       | `S3StorageAdapter`   | ambos implementados |
| `NlpPort`         | `LocalNlpAdapter` (léxico)  | `ComprehendAdapter`  | ambos implementados |
| `TranscriptionPort`| `RecognizeGoogleAdapter` / `MockTranscriptionAdapter` | — | implementado |
| `OcrPort`         | pdfplumber/PyMuPDF + pytesseract | — (nunca Textract) | próxima sessão |
| `SummarizerPort`  | transformers `distilbart`   | Bedrock (fim)        | próxima sessão |

A seleção ocorre em um único lugar (`backend/app/ports/factory.py`), o equivalente
ao registro de serviços de DI do .NET.

## 4. Transcrição de áudio: `recognize_google` (decisão explícita)

**Escolha do autor:** usar `speech_recognition.recognize_google` como backend
padrão de transcrição, alinhado ao material do curso.

⚠️ **Implicação LGPD:** `recognize_google` **envia o áudio para uma API pública do
Google**. Portanto:

- **Nunca** enviar áudio real de paciente por esse caminho.
- Usar apenas **áudio sintético** (voz própria/TTS lendo um relato fictício) nos testes
  e na demo.
- O endpoint `/api/audio/analyze` repete esse aviso na própria documentação.

**Mitigações disponíveis no código:**
- `TRANSCRIPTION_BACKEND=mock` roda a pipeline **offline** (sem enviar nada), usando
  um `.txt` irmão do `.wav`. Bom para testes e CI.
- **Melhoria futura:** adicionar `VoskAdapter` ou `FasterWhisperAdapter` (transcrição
  100% local, sem envio externo). Já previsto na arquitetura — basta um novo adapter.

## 5. Vídeo (YOLOv8): modelo pré-treinado, sem treino customizado

**Decisão:** usar YOLOv8n **pré-treinado** (classes COCO), **sem fine-tuning**.

- **Por quê:** não há dataset clínico rotulado disponível e treinar custaria tempo/recursos
  (restrições de custo e prazo). O modelo pré-treinado é suficiente para demonstrar a
  pipeline ponta a ponta.
- **Como especializamos sem treinar:** a customização fica na **camada de regras de risco**
  (`services/video/risk_rules.py`), não no modelo. Classes COCO funcionam como **proxy**
  (ex.: `knife`, `scissors` → `objeto_suspeito_automutilacao`). As classes-foco são
  **configuráveis** por env (`VIDEO_FOCUS_CLASSES`), então mudar o alvo não exige retreino.
- **Custo zero / offline:** roda 100% local (`VIDEO_BACKEND=local`). Há `MockVideoAdapter`
  (`VIDEO_BACKEND=mock`) para testes/CI sem carregar o modelo. O import de `ultralytics`/`cv2`
  é lazy: o app sobe mesmo sem essas libs.
- **Melhoria futura:** fine-tuning em objetos clínicos reais.

### 5b. Vídeo multimodal opt-in: pose (MediaPipe), emoção (DeepFace) e trilha (MoviePy)

**Decisão:** ampliar o vídeo com três técnicas do material do curso, cada uma atrás de um
Port (local + mock), **opt-in e desligadas por padrão**.

- **Por que default `mock`/`off`:** MediaPipe e DeepFace são libs **pesadas** (DeepFace puxa
  TensorFlow e baixa pesos na 1ª execução; no Windows+Python 3.12 pode haver atrito de
  wheel). Mantendo o default desligado, o app **sobe e `/api/video` funciona igual** sem
  exigir instalá-las — fiel à restrição de custo zero e à subida sem dependências rígidas.
  Ativação consciente na demo: `POSE_BACKEND=local`, `EMOTION_BACKEND=local`,
  `VIDEO_TRANSCREVER_AUDIO=true`.
- **LGPD / dado biométrico:** rosto e pose são **dados sensíveis**. Ainda assim, MediaPipe e
  DeepFace rodam **100% local** — **não enviam nada para fora** (melhor que o
  `recognize_google` do áudio). Usar apenas material **sintético/de domínio público**, nunca
  paciente real. A transcrição da **trilha de áudio** (`VIDEO_TRANSCREVER_AUDIO`) reusa o
  `recognize_google`, então herda o mesmo ⚠️ da §4 (envio ao Google) — por isso fica atrás
  de flag, desligada por padrão.
- **Postura ética:** pose/emoção geram categorias de severidade **média** (`sinal_corporal_estresse`,
  `sinal_emocional_negativo`), **nunca críticas** e **nunca diagnóstico** — apenas indícios
  observáveis para a equipe. Emoção aparente ≠ estado clínico.
- **`face_recognition` (dlib) foi deliberadamente deixado de fora:** o reconhecimento de
  **identidade** exigiria `dlib` (compilação com CMake/VS Build Tools no Windows+Py3.12) e
  não agrega ao caso de uso (queremos indícios, não identificar a pessoa). Fora do escopo.

**Notas de instalação (validado em Python 3.12.10 / Windows):**
- **MediaPipe usa a Tasks API.** A versão instalada (0.10.35) **não tem** a API legada
  `mp.solutions.pose`; o `LocalPoseAdapter` usa `PoseLandmarker` (Tasks) e **baixa o modelo
  `.task` uma vez** do repositório público do Google (como o YOLO baixa `yolov8n.pt`).
  `POSE_MODEL` aponta para um arquivo local para rodar offline.
- **DeepFace exige `tf-keras`** quando o TensorFlow é ≥ 2.16 (Keras 3): `pip install tf-keras`.
  Sem isso, o `retinaface` (dep do DeepFace) falha no import.
- **Conflitos de metadados cosméticos (sem quebra em runtime):** `mediapipe` puxa
  `opencv-contrib-python` (convive com `opencv-python`; o `cv2` resolve para a build contrib)
  e rebaixa `Pillow` (o `pdfplumber` pede ≥12.2 mas funciona com a versão menor). `torch` e
  `tensorflow` **coexistem** no mesmo ambiente sem conflito.
- **Smoke validado:** pose detecta sinais em imagem/vídeo reais; DeepFace classifica emoção
  (rosto real → `neutral`); MoviePy extrai trilha (vídeo com áudio → WAV); e
  `/api/video/analyze` com `POSE_BACKEND=local`/`EMOTION_BACKEND=local` devolve
  `modalidades: ["video","pose","emocao"]` num único alerta.

### 5c. Endpoint único de vídeo + passada única de emoção (consolidação)

**Decisão:** `POST /api/video/emotions` foi **removido**. `POST /api/video/analyze`
passou a ser o **único** ponto de entrada de vídeo/imagem — orquestra internamente YOLO +
pose + emoção + trilha de áudio e devolve tudo num único `AnaliseRiscoResponse`,
incluindo (quando aplicável) o painel `emocao_video` (hexágono + vídeo anotado; ver
relatorio-tecnico.md §4d). O antigo endpoint obrigava o frontend a chamar duas rotas e
costurar o resultado no mesmo card — separação de responsabilidade desnecessária, já que
as duas rotas analisavam o mesmo arquivo.

- **Decisão de design (capacidade no port, não leitura de settings):** em vez de o
  pipeline checar `settings.emotion_backend` para decidir se anota o vídeo, o
  `EmotionPort` ganhou uma capacidade declarada — `suporta_anotacao_video: bool = False`
  na interface, `True` só em `LocalEmotionAdapter`. O pipeline pergunta ao **adapter
  injetado**, não ao settings global. Isso preserva o padrão de DI da §3: os testes
  continuam controlando o comportamento via `dependency_overrides` (injetando
  `MockEmotionAdapter`) sem precisar sincronizar com o `.env` — se a decisão fosse por
  settings, um `.env` local com `EMOTION_BACKEND=local` quebraria silenciosamente os
  testes que substituem o adapter mas não o settings.
- **Passada única do DeepFace:** antes, o risco (`EmotionPort.analisar`) e o painel
  (`anotar_video_emocoes`) rodavam o modelo **separadamente** (2× por vídeo). Agora uma
  única chamada a `anotar_video_emocoes` gera as detecções brutas, das quais tanto a
  categoria `sinal_emocional_negativo` quanto o painel são derivados — metade do custo de
  inferência, mesmo resultado.
- **Sub-recurso de streaming:** `GET /api/video/anotado/{video_id}` (antes
  `GET /api/video/emotions/{video_id}`) serve o MP4 anotado gerado. Não é uma rota de
  análise — é um arquivo já processado, por isso continua existindo separado do
  `/analyze`.
- **Imagem continua sendo o mesmo endpoint que vídeo:** `/api/video/analyze` sempre
  aceitou `.jpg/.png` além de `.mp4/...`; a anotação (hexágono/vídeo) só se aplica a
  vídeo (precisa de múltiplos frames) — para imagem, a emoção segue pelo `EmotionPort`
  normal, como detecção de um frame só.

### Falso positivo conhecido do léxico (limitação honesta)

A detecção de risco por **léxico** (`services/text/risk_lexicon.py`) é proposital —
prioriza **explicabilidade** (cada alerta mostra a expressão que o motivou). O custo
disso é a falta de contexto: uma expressão-gatilho pode disparar uma categoria **fora
do contexto pretendido**.

**Exemplo real (aparece na composição de demo):** o gatilho `"vergonha de contar"`
(pensado para relatos de violência) também aparece em textos de **sofrimento
psíquico** legítimo. No relato de pós-parto usado na demo, a frase *"tenho vergonha de
contar isso pra alguém"* faz o sistema levantar `violencia_domestica` (score baixo,
**0,33**, só do texto), ao lado das categorias corretas de pós-parto.

**Por que isso NÃO é um defeito grave (e reforça a postura do projeto):**
- O alerta é **transparente**: a evidência exibida é exatamente `"tenho vergonha de
  contar"`, então a equipe **vê a origem** e descarta em segundos.
- É a razão de o sistema ser **apoio à decisão, não diagnóstico**: quem valida é o
  profissional. O sistema prefere **errar sinalizando a mais** (recall) a silenciar.
- O score fica **baixo** e **sem corroboração multimodal** (só 1 modalidade), enquanto
  as categorias verdadeiras (`depressao_pos_parto`, `ansiedade`) sobem a **1,0** com
  boost de corroboração — a priorização já separa o sinal do ruído.

**Mitigações futuras previstas:** o `classifier.py` (TF-IDF + Naive Bayes) já complementa
o léxico com uma visão estatística; janelas de contexto/negação e um modelo de linguagem
PT-BR reduziriam esses gatilhos soltos sem perder a explicabilidade.

## 6. Laudos (OCR) e sumarização

- **OCR sem Textract.** `LocalOcrAdapter` extrai texto em cascata **pdfplumber → PyMuPDF →
  pytesseract** (este último só para PDFs imagem). Reafirma a decisão do CLAUDE.md: Textract
  está bloqueado no Free Plan e **não é usado**. Imports lazy; `OCR_BACKEND=mock` para testes.
- **Sumarização local.** `LocalSummarizerAdapter` usa **distilbart-cnn** via
  `AutoModelForSeq2SeqLM` (não `pipeline('summarization')`, cujo alias mudou no
  transformers v5). Default. `ExtractiveSummarizerAdapter` (sem download) é a alternativa
  leve para testes/CI.
- **Limitação assumida:** distilbart-cnn é treinado em inglês → resumo em PT é aproximado.
  Avaliamos com ROUGE (`scripts/avaliar_rouge.py`) contra um resumo de referência sintético.

## 7. Nuvem: decisão oficial e degradação graciosa (testada contra a AWS real)

**Resultado do smoke (`scripts/smoke_aws.py`, executado contra a conta real):**

| Serviço | Resultado | Detalhe |
|---------|-----------|---------|
| **S3** | ✅ funciona | upload + leitura + delete OK (objeto de teste removido no fim). |
| **Comprehend** | ❌ indisponível | `SubscriptionRequiredException`: *"The AWS Access Key Id needs a subscription for the service"*. |

**Decisão oficial de nuvem:**
- **Armazenamento → S3** (`STORAGE_BACKEND=s3`, Always-Free). É o serviço gerenciado de
  nuvem efetivamente usável neste projeto.
- **NLP → local** (`NLP_BACKEND=local`, `LocalNlpAdapter`: léxico PT-BR + classificador
  sklearn). O `ComprehendAdapter` existe e está pronto, mas o **Free Plan por créditos
  bloqueia a subscription** do serviço. **Sem cobrança**: a AWS recusa *antes* de processar.

**Por que isso é uma PROVA do valor de ports/adapters (não uma falha):**
- A indisponibilidade da nuvem foi **absorvida trocando uma única variável de ambiente**
  (`NLP_BACKEND`): routers e serviços não mudaram. O `NlpPort` cai no adapter local e o
  sistema segue **sem perda de função** — o `LocalNlpAdapter` já entrega sentimento,
  entidades e categorias de risco **explicáveis** (com evidências).
- Ou seja, projetamos para **degradação graciosa** e isso foi **testado contra a AWS real**,
  não só no papel. É exatamente o cenário que o padrão previa.

**Conformidade (LGPD):** o smoke trafegou **apenas texto sintético** (laudo fictício);
nenhum PHI. Reforça a postura de dados sintéticos de todo o projeto.

**Ferramenta:** `scripts/smoke_aws.py` é **opt-in** (`RUN_AWS_SMOKE=1` + credenciais no
`.env`) e **não roda no pytest** — a lógica de mapeamento dos adapters é testada com
clients falsos, então a suíte passa **sem AWS**.

## 8. Segredos e dados

- `.env` está no `.gitignore`; só `.env.example` é versionado.
- `.gitignore` cobre modelos pesados (`*.pt`, `*.onnx`), `data/` real, `venv/`, e os
  exemplos gerados (`data/samples/*.mp4`, `*.pdf`, `demo_yolo.jpg`).
- Apenas `data/samples/` (texto sintético) é versionado; vídeos/PDFs de exemplo são
  **gerados sob demanda** (`scripts/gerar_video_exemplo.py`, `scripts/gerar_laudo_exemplo.py`).

## 9. Ambiente

- O CLAUDE.md prevê Python 3.11; a máquina local usa **Python 3.12** (compatível).
  `requirements.txt` usa faixas `>=` para evitar quebra de instalação no 3.12.
