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

| Serviço      | Decisão                                                        |
|--------------|---------------------------------------------------------------|
| **S3**       | OK usar (Always-Free). `S3StorageAdapter` opcional.           |
| Comprehend   | Só na demo final. `ComprehendAdapter` opcional; default local.|
| Rekognition  | Não usar (visão é local — YOLOv8/DeepFace/MediaPipe).         |
| Bedrock      | Só na demo final, poucas chamadas, se sobrar crédito.         |
| **Textract** | **Bloqueado / não usar.** OCR de laudos será 100% local.     |

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

## 5. Segredos e dados

- `.env` está no `.gitignore`; só `.env.example` é versionado.
- `.gitignore` cobre modelos pesados (`*.pt`, `*.onnx`), `data/` real, `venv/`.
- Apenas `data/samples/` (sintético) é versionado.

## 6. Ambiente

- O CLAUDE.md prevê Python 3.11; a máquina local usa **Python 3.12** (compatível).
  `requirements.txt` usa faixas `>=` para evitar quebra de instalação no 3.12.
