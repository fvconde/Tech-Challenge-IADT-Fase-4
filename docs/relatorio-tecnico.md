# Relatório Técnico — Tech Challenge Fase 4

> Relatório técnico da solução: cobre o **fluxo multimodal**, os **modelos por tipo de
> dado** e os **resultados reais** obtidos. As decisões de LGPD, custo e nuvem estão em
> [decisoes-arquiteturais.md](decisoes-arquiteturais.md).

## 0. Conformidade com o brief (auditoria)

Os **três itens obrigatórios** do desafio, e onde cada um é atendido:

| Item obrigatório do brief                         | Onde no relatório | Status |
|---------------------------------------------------|-------------------|--------|
| **(a)** Fluxo multimodal                          | §2 (diagrama + endpoints) e §5 (regra de fusão) | ✅ |
| **(b)** Modelos por tipo de dado                  | §3 (tabela por modalidade), §4 (YOLOv8), §4b (OCR + sumarização) | ✅ |
| **(c)** Resultados reais + exemplos de anomalias  | §6 (saídas reais, **composição de demo validada** com 3 modalidades, ROUGE, detecções YOLOv8 reais) | ✅ |

Requisitos de escopo da versão "Secretaria": **3 funcionalidades** (áudio, vídeo/YOLOv8,
nuvem — exige ≥2) e **4 objetivos** (risco materno/ginecológico, violência, bem-estar
psicológico, nuvem — exige ≥3). YOLOv8 **obrigatório**: atendido com detecção real
(§4, §6). Detalhes de LGPD/custo/nuvem em
[decisoes-arquiteturais.md](decisoes-arquiteturais.md).

## 1. Visão geral da solução

IA multimodal de **apoio à decisão clínica** em saúde e segurança da mulher. Processa
**texto, áudio, vídeo e laudos (PDF)** para identificar precocemente sinais de risco e
**gerar alertas para a equipe especializada** — sem emitir diagnóstico.

Funcionalidades escolhidas (≥ 2 exigidas): **áudio**, **vídeo (YOLOv8)** e **nuvem (opcional)**.
Objetivos escolhidos (≥ 3 exigidos): risco materno/ginecológico, violência doméstica,
bem-estar psicológico, uso de nuvem para ampliar capacidade.

## 2. Fluxo multimodal

```
TEXTO  --> LocalNlpAdapter (sentimento+entidades) ----\
ÁUDIO  --> TranscriptionPort --> texto ---------------> categorias de risco (texto) --\
           (recognize_google)                                                          \
LAUDO  --> OcrPort (pdfplumber) --> texto + Summarizer -> categorias de risco (laudo) --> FUSÃO
           (PDF, 100% local)                                                            /   |
VÍDEO  --> VideoPort (YOLOv8) --> detecções COCO --> regras de risco --> categorias ---/   |
                                  (knife/scissors)   (pós-processamento)   (vídeo)          v
                                                                          nível de alerta + ação
                                                                          -> equipe especializada
```

A **fusão** (`services/fusion`) combina as categorias de **todas** as modalidades em um
alerta único. Endpoints: `/api/text/analyze`, `/api/audio/analyze`, `/api/video/analyze`,
`/api/laudo/analyze` e `/api/fusion/analyze` (texto + vídeo + laudo juntos). Tudo roda
**100% local** por padrão; a nuvem (AWS) é opcional.

> `GET /api/video/anotado/{video_id}` é um **sub-recurso** (streaming do vídeo anotado
> com rosto+emoção, gerado por um `/analyze` anterior) — não é uma rota de análise
> adicional. Ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md) §5c.

## 3. Modelos e técnicas por tipo de dado

| Modalidade | Técnica / Modelo                          | Biblioteca            | Local? |
|------------|-------------------------------------------|-----------------------|--------|
| Texto      | Sentimento por léxico PT-BR               | (próprio)             | ✅     |
| Texto      | Classificador de risco TF-IDF + NaiveBayes| scikit-learn          | ✅     |
| Texto      | Extração de entidades (regex)             | (próprio)             | ✅     |
| Áudio      | Transcrição fala→texto                     | SpeechRecognition (recognize_google) | ⚠️ envia ao Google |
| Vídeo      | Detecção de objetos                        | ultralytics (YOLOv8n) | ✅     |
| Vídeo      | Pose / atividade corporal (opt-in)         | MediaPipe (Tasks API `PoseLandmarker`) | ✅ (baixa modelo `.task` 1×) |
| Vídeo      | Emoção facial (opt-in)                      | DeepFace              | ✅ (baixa pesos 1×) |
| Vídeo      | Trilha de áudio → transcrição (opt-in)     | MoviePy (+ SpeechRecognition) | ⚠️ trilha vai ao Google se ativa |
| Laudo      | Extração de texto de PDF (OCR)             | pdfplumber / PyMuPDF / pytesseract | ✅ (sem Textract) |
| Laudo      | Sumarização abstrativa                     | transformers (distilbart-cnn) | ✅ |
| Nuvem      | Armazenamento (**usado**)                  | Amazon S3             | ☁️ ✅ funciona |
| Nuvem      | Sentimento/entidades                       | Amazon Comprehend     | ☁️ ❌ indisponível → NLP local |

> **Áudio:** a modalidade de áudio reusa **todo** o pipeline de texto — a fala é
> transcrita (`recognize_google`) e o texto passa pelo **mesmo** léxico PT-BR +
> classificador sklearn, virando a modalidade `audio` na fusão.
>
> **Nuvem (real):** o smoke contra a conta AWS confirmou **S3 funcionando** e
> **Comprehend indisponível** (`SubscriptionRequiredException`, Free Plan por créditos,
> sem cobrança). O sistema usa **S3** para armazenamento e **NLP local** (degradação
> graciosa via ports/adapters). Detalhe em [decisoes-arquiteturais.md](decisoes-arquiteturais.md) §7.

## 4. Modelo de vídeo (YOLOv8) e regras de risco

- **Modelo:** YOLOv8n **pré-treinado** (`ultralytics`), classes COCO genéricas.
  **Sem treino customizado** (sem dataset rotulado; restrição de custo/tempo —
  ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md)).
- **Customização = pós-processamento.** A especialização para o nosso caso não está
  no modelo, e sim em **regras de risco** (`services/video/risk_rules.py`): classes-foco
  configuráveis (`VIDEO_FOCUS_CLASSES`, default `knife,scissors`) viram a categoria
  `objeto_suspeito_automutilacao`. Trocar o alvo não exige mexer no modelo.
- **Amostragem de frames:** em vídeos, processa **1 frame a cada N** (`VIDEO_FRAME_SAMPLE`,
  default 15) via `cv2.VideoCapture`, para reduzir custo. Imagens são 1 inferência.
- **Score visual:** maior confiança entre as detecções-foco; evidências no formato
  `"knife (conf 0.82, frame 30)"` (rastreabilidade).

## 4b. Modelo de documento (laudo): OCR + sumarização

- **Extração de texto (OcrPort → LocalOcrAdapter):** cascata **100% local**
  `pdfplumber` (default) → `PyMuPDF` (fallback) → `pytesseract` (OCR, só se o PDF for
  imagem/escaneado). **NUNCA Textract** (bloqueado no Free Plan). O laudo extraído passa
  pelo **mesmo** léxico + classificador do texto, virando a modalidade `laudo` na fusão.
- **Sumarização (SummarizerPort):**
  - `LocalSummarizerAdapter` — abstrativa com **distilbart-cnn** (`transformers`,
    `AutoModelForSeq2SeqLM`). Default.
  - `ExtractiveSummarizerAdapter` — extrativa (primeiras frases), instantânea, sem
    download. Usada nos testes e como alternativa leve (`SUMMARIZER_BACKEND=extractive`).
- **Avaliação ROUGE** (`scripts/avaliar_rouge.py`): resumo do distilbart vs. um resumo
  de referência sintético (`data/samples/laudo_exemplo_resumo_ref.txt`).

  | Métrica  | F1     |
  |----------|--------|
  | ROUGE-1  | 0,350  |
  | ROUGE-2  | 0,103  |
  | ROUGE-L  | 0,300  |

  (Medido no laudo sintético `laudo_exemplo.txt` vs. `laudo_exemplo_resumo_ref.txt`.)

  > Nota: distilbart-cnn é treinado em **inglês** (CNN/DailyMail); em português o resumo é
  > aproximado e o ROUGE tende a ser modesto. O número serve de baseline reprodutível.

## 4c. Vídeo multimodal: pose (MediaPipe), emoção (DeepFace) e trilha de áudio (MoviePy)

O endpoint `/api/video/analyze` é um analisador **multimodal** do mesmo arquivo — YOLO
(sempre) + três técnicas **opt-in**, cada uma atrás de um Port com adapter local + mock:

- **Pose / atividade (MediaPipe → `PosePort` → `pose_rules.py`):** os 33 landmarks viram
  **sinais corporais** por heurísticas conservadoras (`maos_proximas_ao_rosto`,
  `maos_juntas_ao_corpo`) → categoria `sinal_corporal_estresse`.
- **Emoção facial (DeepFace → `EmotionPort` → `emotion_rules.py`):** só emoções
  **negativas** (`sad`/`fear`/`angry`/`disgust`) acima do limiar viram
  `sinal_emocional_negativo`. Emoções positivas não geram risco.
- **Trilha de áudio (MoviePy → `TranscriptionPort` → NLP):** extrai o áudio do vídeo,
  transcreve e reusa **todo** o pipeline de texto, virando a modalidade `audio` na fusão.

**Padrão de custo/segurança:** defaults `POSE_BACKEND=mock`, `EMOTION_BACKEND=mock`,
`VIDEO_TRANSCREVER_AUDIO=false` → o app sobe e o endpoint se comporta como antes (só YOLO)
**sem** exigir as libs pesadas. Ativação na demo: `POSE_BACKEND=local`,
`EMOTION_BACKEND=local`, `VIDEO_TRANSCREVER_AUDIO=true`. Cada técnica é **isolada**: falha
de uma (lib ausente, sem rosto, sem trilha) não derruba as demais. **Nenhum diagnóstico:**
pose e emoção são categorias de severidade **média** (não críticas), só indícios para a equipe.

## 4d. Painel de emoção: hexágono e vídeo anotado

Quando `EMOTION_BACKEND=local` e o arquivo é **vídeo**, `POST /api/video/analyze` (e a
fusão, quando há vídeo entre as entradas) devolve também o bloco `emocao_video` embutido
na resposta:

- **Perfil (hexágono):** intensidade média de 6 emoções — medo, tristeza, raiva, aversão,
  surpresa, neutro — nos frames em que houve rosto (0 a 1 por eixo).
- **Timeline:** emoção dominante por frame amostrado, com o instante em segundos.
- **`dominante_geral`:** emoção que mais pesou no vídeo inteiro.
- **Vídeo anotado (URL):** MP4 com a caixa do rosto e o rótulo da emoção desenhados
  frame a frame (`cv2.rectangle`/`cv2.putText`), servido por
  `GET /api/video/anotado/{video_id}`.

Esse painel é gerado pela **mesma passada** do DeepFace que produz a categoria de risco
`sinal_emocional_negativo` (ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md)
§5c) — não há uma segunda inferência para montar o gráfico.

## 5. Categorias de risco e regra de fusão

Categorias monitoradas: `depressao_pos_parto`, `ansiedade`, `violencia_domestica`,
`fadiga_hormonal` (texto/áudio), `objeto_suspeito_automutilacao` (vídeo/YOLO) e — quando as
técnicas opt-in estão ativas — `sinal_corporal_estresse` (vídeo/pose) e
`sinal_emocional_negativo` (vídeo/emoção). Cada alerta carrega as **evidências** que o
motivaram.

**Regra de fusão multimodal** (`services/fusion/alerts.py` + `multimodal.py`):
1. Cada modalidade produz uma lista de `DeteccaoCategoria` (mesmo tipo de dado).
2. `combinar_categorias` junta as listas; categoria repetida → **maior score + união de
   evidências**; se a mesma categoria vier de **≥2 modalidades**, aplica **boost de
   corroboração** (+0,15, saturado em 1,0).
3. Categorias **críticas** (`violencia_domestica`, `objeto_suspeito_automutilacao`) com
   qualquer indício → alerta **ALTO**.
4. Caso geral: nível pelo maior score **ponderado pela severidade** da categoria
   (`alto ≥ 0,6`, `medio ≥ 0,3`, senão `baixo`).

**Categorização por trecho (achados).** Além do agregado acima (que decide o alerta),
`services/text/achados.py` quebra texto/transcrição/laudo em frases e classifica **cada
frase** contra o léxico, gerando `achados: list[AchadoTrecho]` — um registro por
(trecho × categoria) com `fonte`, `trecho`, `categoria`, `score` e `metadados`
(ex.: `indice_trecho`). É aditivo (não muda o alerta) e existe para rastreabilidade fina:
qual frase exata motivou cada indício, de qual modalidade. Detalhe da decisão (e por que
não adotamos RAG/embeddings/LLM para isso) em
[decisoes-arquiteturais.md](decisoes-arquiteturais.md) §5d.

## 6. Resultados obtidos e exemplos (saídas reais)

**Texto** (amostras sintéticas em `data/samples/`):

| Amostra                  | Nível | Categoria principal               |
|--------------------------|-------|-----------------------------------|
| consulta_pos_parto       | alto  | depressao_pos_parto (1.0)         |
| triagem_violencia        | alto  | violencia_domestica (1.0)         |
| pre_natal_ansiedade      | médio/alto | ansiedade                    |
| consulta_rotina_ok       | baixo | — (sem risco)                     |

**Vídeo** (smoke real do `LocalVideoAdapter` em `data/samples/`):

- Imagem `demo_yolo.jpg`: detectou `bus`, `person`×4, `stop sign` → nenhuma classe-foco
  → risco **baixo** (correto).
- Vídeo `video_exemplo.mp4` (20 frames, 4 amostrados): detectou `bus`/`person` → **baixo**.
- Imagem `tesoura.jpg` (**detecção YOLOv8 real**): detectou `scissors` (**conf 0,85**),
  `person` e mais 2 `scissors` → classe-foco → `objeto_suspeito_automutilacao`
  (**score 0,848**) → alerta **alto**, com **imagem anotada** (bounding boxes) no response.
  É o caso "alto" com modelo real usado na demo.

**Vídeo multimodal — pose/emoção** (smoke real com `POSE_BACKEND=local` e
`EMOTION_BACKEND=local` no clipe `paciente_demoV2.mp4` — **vídeo sintético gerado por IA**, ver §7):

- **Emoção (DeepFace):** rosto detectado nos frames amostrados; emoções aparentes
  `fear`/`sad`/`surprise`, com **pico de medo 0,999** → categoria `sinal_emocional_negativo`
  (**score 0,999**).
- **Pose (MediaPipe):** sinal `maos_juntas_ao_corpo` (**conf 0,98**) → categoria
  `sinal_corporal_estresse` (**score 0,98**).
- **YOLO:** `person` (conf 0,92) em todos os frames — nenhuma classe-foco.
- **Alerta (só vídeo):** **médio**, `modalidades: ["video","pose","emocao"]` — as **três**
  técnicas de visão convergindo no mesmo arquivo. Médio é o esperado: pose e emoção são
  indícios de severidade média (não críticos); na fusão com texto/laudo o alerta sobe a **alto**.

> Um clipe *close-up* anterior (`paciente_demo.mp4`) deu emoção 0,881 mas **0 sinais de
> pose** — a sensibilidade ao enquadramento e a mitigação são discutidas no §7.

**Vídeo com trilha de áudio — 4 modalidades num único arquivo** (smoke real; ao vídeo
sintético foi acoplada uma **fala sintética** gerada por TTS — `edge-tts`, PT-BR —, também
sem voz real, ver §7). Com `VIDEO_TRANSCREVER_AUDIO=true`, o `/api/video/analyze` extrai a
trilha (MoviePy), transcreve (`recognize_google`) e roda o NLP:

- **Transcrição (real):** *"tenho medo dele ele me empurrou e me ameaçou"*.
- **Modalidade `audio`:** `violencia_domestica` (**crítica, score 1,0**) — evidências
  `tenho medo dele`, `me empurrou`, `me ameacou`.
- **Emoção:** `sinal_emocional_negativo` **0,999**; **Pose:** `sinal_corporal_estresse`
  **0,977**; **YOLO:** `person`.
- **Resultado:** `modalidades: ["audio","video","pose","emocao"]`, nível **ALTO** (a
  categoria crítica de violência domina), com ação prioritária de protocolo de violência.

É o exemplo multimodal mais completo: **um só arquivo** exercitando fala→NLP + emoção +
pose + objeto, convergindo num alerta único, priorizado e rastreável.

> **Paridade com a fusão (correção aplicada):** esse mesmo resultado (trilha → NLP →
> `violencia_domestica` crítica → ALTO) hoje também é alcançado via
> `/api/fusion/analyze` quando o vídeo é uma das entradas. Antes, a fusão **não**
> transcrevia a trilha do próprio vídeo — um risco só audível na fala podia então
> desaparecer na fusão, produzindo um nível **mais fraco** que a análise isolada do
> mesmo arquivo (o oposto do princípio de corroboração da fusão). Corrigido: a fusão
> agora repassa `transcription`/`nlp`/`transcrever_audio` ao analisar o(s) visual(is) e
> soma essas categorias à modalidade `audio` (o `audio_arquivo` dedicado, quando
> presente, tem prioridade na transcrição exibida).

**Laudo** (smoke real do `LocalOcrAdapter` no PDF sintético `laudo_exemplo.pdf`):

- OCR: `pdfplumber`, 1 página, sem precisar de OCR de imagem.
- Risco: `ansiedade` (1.0) + `depressao_pos_parto` (0.333), sentimento negativo → **alto**.
- Resumo gerado e devolvido na resposta.

**Fusão — composição de demo validada** (`/api/fusion/analyze`, saída real):

Entradas: **texto** = relato de pós-parto (exemplo "Pós-parto"); **imagem** =
`tesoura.jpg`; **laudo** = `laudo_exemplo.pdf` (pós-parto). Resultado:
`modalidades: ["texto","video","laudo"]`, nível **ALTO**.

| Categoria                        | Score | Origem / evidência                                   |
|----------------------------------|-------|------------------------------------------------------|
| `depressao_pos_parto`            | 1,000 | texto + laudo — **corroboração multimodal (2 modalidades)** |
| `ansiedade`                      | 1,000 | texto + laudo — **corroboração multimodal (2 modalidades)** |
| `objeto_suspeito_automutilacao`  | 0,848 | vídeo — `scissors` (conf 0,85) + **imagem anotada**  |
| `violencia_domestica`            | 0,333 | **falso positivo** do léxico (só texto; ver §7)      |
| `fadiga_hormonal`                | 0,333 | texto — `"exausta"`                                  |

Este é o **exemplo de anomalia** central do desafio: três tipos de dado diferentes
(texto, imagem, documento) convergindo em **um alerta único, priorizado e rastreável**.
A **corroboração** (texto+laudo apontando a mesma categoria) eleva os scores a 1,0, e a
categoria **crítica** de vídeo garante o nível **alto** — enquanto o falso positivo fica
com score baixo e sem corroboração, demonstrando que a **priorização separa sinal de
ruído**. Casos "alto" adicionais (violência + objeto de vídeo etc.) são cobertos pelos
testes automatizados.

**Nuvem (resultado real, smoke contra a conta AWS):**
- **S3:** ✅ upload + leitura + limpeza do laudo sintético OK.
- **Comprehend:** ❌ `SubscriptionRequiredException` (Free Plan por créditos, **sem
  cobrança**) → o `NlpPort` cai no `LocalNlpAdapter` sem perda de função. **Prova de
  degradação graciosa** do padrão ports/adapters, validada contra a AWS real.

**Testes:** 54 casos automatizados passando (`pytest backend/tests`).

## 7. Conformidade e limitações

- Sem PHI; apenas dados sintéticos (LGPD). Ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md).
- **Vídeo de "paciente" gerado por IA:** o clipe usado para exercitar emoção/pose
  (`paciente_demoV2.mp4`) é **sintético** (produzido por ferramenta de vídeo por IA), não é
  pessoa real — reforço direto de LGPD (sem rosto nem PHI de paciente).
- **Fala de "paciente" gerada por TTS:** o áudio acoplado ao vídeo (`fala.mp3`, via
  `edge-tts`) é **voz sintética**, não é gravação real — mesmo racional de LGPD do vídeo
  sintético. A transcrição ainda envia o áudio ao Google (`recognize_google`), por isso só
  material sintético.
- `recognize_google` envia áudio a terceiros — usar só material sintético; backend
  offline previsto como melhoria.
- **Amazon Comprehend** ficou **indisponível na conta** (`SubscriptionRequiredException`,
  Free Plan por créditos; **sem cobrança**). O sistema usa o `LocalNlpAdapter` (default) —
  degradação graciosa via ports/adapters, **sem perda de função**. Se um dia for habilitado,
  lembrar que ele envia texto a terceiros (AWS) → só com dado sintético.
- Extração de laudo é **100% local** (pdfplumber/PyMuPDF/pytesseract) — Textract não é usado.
- distilbart-cnn é treinado em inglês; resumo em português é aproximado.
- Léxico/classificador são propositais e **explicáveis**, mas têm cobertura limitada;
  não substituem avaliação profissional.
- **Falso positivo conhecido do léxico:** por priorizar explicabilidade, uma
  expressão-gatilho pode disparar uma categoria fora de contexto. Ex. real (aparece na
  composição de demo): `"vergonha de contar"` levanta `violencia_domestica` (score baixo,
  0,33) num relato de pós-parto. O alerta é transparente (mostra a evidência), fica com
  score baixo e **sem corroboração**, e cabe à equipe validar — coerente com a postura de
  **apoio à decisão, não diagnóstico**. Detalhe e mitigações em
  [decisoes-arquiteturais.md](decisoes-arquiteturais.md) §5.
- Vídeo usa modelo pré-treinado em classes COCO (proxy). Fine-tuning é melhoria futura.
- **Pose (MediaPipe) é sensível ao enquadramento:** as heurísticas exigem punhos e nariz
  visíveis (pulso próximo ao nariz / pulsos juntos). Num vídeo *close-up* (`paciente_demo.mp4`)
  punhos e tórax saem do quadro e **nenhum** sinal corporal é gerado; num enquadramento aberto
  (cintura para cima, `paciente_demoV2.mp4`) o sinal `maos_juntas_ao_corpo` foi detectado a
  **0,98** — **mitigação confirmada** (§6).

## 8. Como reproduzir

Ver [README.md](../README.md) (setup, execução da API, testes). Atalhos:
- Vídeo: `python scripts/gerar_video_exemplo.py` → `POST /api/video/analyze`.
- Laudo: `python scripts/gerar_laudo_exemplo.py` → `POST /api/laudo/analyze`.
- ROUGE: `python scripts/avaliar_rouge.py`.
- Nuvem (opt-in, precisa de credenciais): `RUN_AWS_SMOKE=1 python scripts/smoke_aws.py`.
