# data/

> 🔒 **LGPD:** este diretorio NUNCA deve conter dados reais de pacientes (PHI).
> Apenas material **sintetico** ou de dominio publico.

## Estrutura

- `samples/` — exemplos **sinteticos** (versionados) para testar a pipeline.
  - `*.txt` — relatos de consulta ficticios.
  - Para audio: grave um WAV lendo um dos `.txt` (a transcricao devolvera o texto).
- `storage/` — saida do `LocalStorageAdapter` em tempo de execucao (**ignorado** pelo git).
- `raw/`, `processed/`, `uploads/`, `output/` — areas de trabalho locais (**ignoradas**).

## Como gerar um WAV de teste (Windows, sem instalar nada)

Use a sintese de voz do Windows para "ler" um relato sintetico e gerar um WAV:

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("data/samples/consulta_pos_parto.wav")
$s.Speak((Get-Content -Raw data/samples/consulta_pos_parto.txt))
$s.Dispose()
```

> Observacao: a voz padrao do Windows costuma ser em ingles. Para um teste de
> transcricao PT-BR de boa qualidade, grave sua propria voz lendo o `.txt`,
> ou instale uma voz PT-BR do Windows. O conteudo continua 100% sintetico.
