# Relatório Técnico — Tech Challenge Fase 4

> Documento em construção. Esqueleto criado na Sessão 1; será preenchido com
> resultados e exemplos ao longo do desenvolvimento.

## 1. Visão geral da solução

IA multimodal de **apoio à decisão clínica** em saúde e segurança da mulher. Processa
**texto, áudio e vídeo** para identificar precocemente sinais de risco e
**gerar alertas para a equipe especializada** — sem emitir diagnóstico.

Funcionalidades escolhidas (≥ 2 exigidas): **áudio**, **vídeo (YOLOv8)** e **nuvem (opcional)**.
Objetivos escolhidos (≥ 3 exigidos): risco materno/ginecológico, violência doméstica,
bem-estar psicológico, uso de nuvem para ampliar capacidade.

## 2. Fluxo multimodal

```
TEXTO  --> LocalNlpAdapter (sentimento+entidades) ----\
ÁUDIO  --> TranscriptionPort --> texto ---------------> categorias de risco (texto) --\
           (recognize_google)                                                          \
                                                                                        > FUSÃO
VÍDEO  --> VideoPort (YOLOv8) --> detecções COCO --> regras de risco --> categorias ---/   |
                                  (knife/scissors)   (pós-processamento)   (vídeo)          v
                                                                          nível de alerta + ação
                                                                          -> equipe especializada
```

A **fusão** (`services/fusion`) combina as categorias de **todas** as modalidades em um
alerta único. Endpoints: `/api/text/analyze`, `/api/audio/analyze`, `/api/video/analyze`
e `/api/fusion/analyze` (texto + vídeo juntos). Tudo roda **100% local** por padrão.

## 3. Modelos e técnicas por tipo de dado

| Modalidade | Técnica / Modelo                          | Biblioteca            | Local? |
|------------|-------------------------------------------|-----------------------|--------|
| Texto      | Sentimento por léxico PT-BR               | (próprio)             | ✅     |
| Texto      | Classificador de risco TF-IDF + NaiveBayes| scikit-learn          | ✅     |
| Texto      | Extração de entidades (regex)             | (próprio)             | ✅     |
| Áudio      | Transcrição fala→texto                     | SpeechRecognition (recognize_google) | ⚠️ envia ao Google |
| Vídeo      | Detecção de objetos                        | ultralytics (YOLOv8n) | ✅     |
| Nuvem (opc)| Sentimento/entidades                       | Amazon Comprehend     | ☁️     |
| Nuvem (opc)| Armazenamento                              | Amazon S3             | ☁️     |

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
- Caminho **alto** (objeto-foco): coberto pelos testes com `MockVideoAdapter`
  (`knife`/`scissors` → `objeto_suspeito_automutilacao` → alerta **alto**). Para um demo
  "alto" com modelo real, usar um clipe/imagem contendo faca ou tesoura.

**Fusão** (`/api/fusion/analyze`): texto de violência + vídeo com `knife` →
modalidades `["texto","video"]`, categorias `violencia_domestica` + `objeto_suspeito_automutilacao`,
nível **alto**.

**Testes:** 20 casos automatizados passando (`pytest backend/tests`).

## 7. Conformidade e limitações

- Sem PHI; apenas dados sintéticos (LGPD). Ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md).
- `recognize_google` envia áudio a terceiros — usar só material sintético; backend
  offline previsto como melhoria.
- Léxico/classificador são propositais e **explicáveis**, mas têm cobertura limitada;
  não substituem avaliação profissional.
- Vídeo usa modelo pré-treinado em classes COCO (proxy). As classes-foco são uma
  aproximação; um modelo fine-tuned em objetos clínicos é melhoria futura.

## 8. Como reproduzir

Ver [README.md](../README.md) (setup, execução da API, testes e notebook). Para o vídeo:
`python scripts/gerar_video_exemplo.py` e depois `POST /api/video/analyze`.
