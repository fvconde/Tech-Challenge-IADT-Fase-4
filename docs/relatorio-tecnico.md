# Relatório Técnico — Tech Challenge Fase 4

> Documento em construção. Esqueleto criado na Sessão 1; será preenchido com
> resultados e exemplos ao longo do desenvolvimento.

## 1. Visão geral da solução

IA multimodal de **apoio à decisão clínica** em saúde e segurança da mulher. Processa
**texto, áudio e (vídeo, via notebook)** para identificar precocemente sinais de risco e
**gerar alertas para a equipe especializada** — sem emitir diagnóstico.

Funcionalidades escolhidas (≥ 2 exigidas): **áudio**, **vídeo (YOLOv8)** e **nuvem (opcional)**.
Objetivos escolhidos (≥ 3 exigidos): risco materno/ginecológico, violência doméstica,
bem-estar psicológico, uso de nuvem para ampliar capacidade.

## 2. Fluxo multimodal

```
TEXTO  --> LocalNlpAdapter (sentimento+entidades) --\
                                                     \
ÁUDIO  --> TranscriptionPort --> texto -------------> Análise de risco
           (recognize_google)                         (léxico + classificador)
                                                     /          |
VÍDEO  --> YOLOv8 (notebook, Sessão 1) ------------/           v
                                              Fusão de sinais -> nível de alerta
                                                                + ação recomendada
                                                                -> equipe especializada
```

Na Sessão 1, a **fusão** combina os sinais de texto/áudio. A entrada de vídeo na fusão
via API está no roadmap.

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

## 4. Detecção de anomalias / categorias de risco

Categorias monitoradas no texto/áudio: `depressao_pos_parto`, `ansiedade`,
`violencia_domestica`, `fadiga_hormonal`. Cada alerta carrega as **evidências**
(expressões que o motivaram), garantindo rastreabilidade. Violência doméstica
escala sempre para alerta **alto**.

## 5. Resultados obtidos e exemplos

> A preencher com saídas reais da API e do notebook.

- [ ] Exemplo de análise de texto (4 amostras sintéticas) — ver `data/samples/`.
- [ ] Exemplo de análise de áudio (WAV sintético).
- [ ] Saída do YOLOv8 no notebook (imagem anotada + tabela de detecções).
- [ ] Exemplo de alerta final gerado para a equipe.

## 6. Conformidade e limitações

- Sem PHI; apenas dados sintéticos (LGPD). Ver [decisoes-arquiteturais.md](decisoes-arquiteturais.md).
- `recognize_google` envia áudio a terceiros — usar só material sintético; backend
  offline previsto como melhoria.
- Léxico/classificador são propositais e **explicáveis**, mas têm cobertura limitada;
  não substituem avaliação profissional.

## 7. Como reproduzir

Ver [README.md](../README.md) (setup, execução da API, testes e notebook).
