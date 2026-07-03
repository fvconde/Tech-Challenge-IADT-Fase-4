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

## 3. Modelos e técnicas por tipo de dado

| Modalidade | Técnica / Modelo                          | Biblioteca            | Local? |
|------------|-------------------------------------------|-----------------------|--------|
| Texto      | Sentimento por léxico PT-BR               | (próprio)             | ✅     |
| Texto      | Classificador de risco TF-IDF + NaiveBayes| scikit-learn          | ✅     |
| Texto      | Extração de entidades (regex)             | (próprio)             | ✅     |
| Áudio      | Transcrição fala→texto                     | SpeechRecognition (recognize_google) | ⚠️ envia ao Google |
| Vídeo      | Detecção de objetos                        | ultralytics (YOLOv8n) | ✅     |
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

## 5. Categorias de risco e regra de fusão

Categorias monitoradas: `depressao_pos_parto`, `ansiedade`, `violencia_domestica`,
`fadiga_hormonal` (texto/áudio) e `objeto_suspeito_automutilacao` (vídeo). Cada alerta
carrega as **evidências** que o motivaram.

**Regra de fusão multimodal** (`services/fusion/alerts.py` + `multimodal.py`):
1. Cada modalidade produz uma lista de `DeteccaoCategoria` (mesmo tipo de dado).
2. `combinar_categorias` junta as listas; categoria repetida → **maior score + união de
   evidências**; se a mesma categoria vier de **≥2 modalidades**, aplica **boost de
   corroboração** (+0,15, saturado em 1,0).
3. Categorias **críticas** (`violencia_domestica`, `objeto_suspeito_automutilacao`) com
   qualquer indício → alerta **ALTO**.
4. Caso geral: nível pelo maior score **ponderado pela severidade** da categoria
   (`alto ≥ 0,6`, `medio ≥ 0,3`, senão `baixo`).

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

**Testes:** 30 casos automatizados passando (`pytest backend/tests`).

## 7. Conformidade e limitações

- Sem PHI; apenas dados sintéticos (LGPD). Ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md).
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

## 8. Como reproduzir

Ver [README.md](../README.md) (setup, execução da API, testes). Atalhos:
- Vídeo: `python scripts/gerar_video_exemplo.py` → `POST /api/video/analyze`.
- Laudo: `python scripts/gerar_laudo_exemplo.py` → `POST /api/laudo/analyze`.
- ROUGE: `python scripts/avaliar_rouge.py`.
- Nuvem (opt-in, precisa de credenciais): `RUN_AWS_SMOKE=1 python scripts/smoke_aws.py`.
