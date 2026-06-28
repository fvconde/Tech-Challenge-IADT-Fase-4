"""
Adapters de transcricao de audio (TranscriptionPort).

- RecognizeGoogleAdapter: usa speech_recognition.recognize_google (DEFAULT escolhido).
  ATENCAO LGPD: este metodo ENVIA o audio para uma API publica do Google. Para dados
  de saude isso e uma escolha que esta DOCUMENTADA em docs/decisoes-arquiteturais.md.
  Alternativa offline futura: vosk / faster-whisper.
- MockTranscriptionAdapter: nao usa rede. Le um arquivo .txt "irmao" do .wav
  (mesmo nome, extensao .txt) ou devolve texto fixo. Serve para testes e para rodar
  a pipeline OFFLINE sem depender da internet.

speech_recognition le WAV/AIFF/FLAC nativamente (sem ffmpeg). Outros formatos
exigiriam pydub + ffmpeg (fora do escopo desta fatia).
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.app.ports.base import TranscriptionPort, TranscriptionResult

logger = logging.getLogger(__name__)


class RecognizeGoogleAdapter(TranscriptionPort):
    """Transcricao via Google Web Speech API (recognize_google). Requer internet."""

    def transcrever(self, caminho_wav: str, idioma: str = "pt-BR") -> TranscriptionResult:
        try:
            import speech_recognition as sr  # lazy
        except ImportError as exc:
            raise RuntimeError(
                "RecognizeGoogleAdapter requer SpeechRecognition. "
                "Instale com 'pip install SpeechRecognition' ou use TRANSCRIPTION_BACKEND=mock."
            ) from exc

        recognizer = sr.Recognizer()
        with sr.AudioFile(caminho_wav) as fonte:
            audio = recognizer.record(fonte)

        try:
            texto = recognizer.recognize_google(audio, language=idioma)
        except sr.UnknownValueError:
            logger.warning("Audio nao compreendido pela API (%s).", caminho_wav)
            texto = ""
        except sr.RequestError as exc:
            raise RuntimeError(
                f"Falha ao contatar a API de transcricao do Google: {exc}. "
                "Verifique a conexao ou use TRANSCRIPTION_BACKEND=mock."
            ) from exc

        logger.info("Transcricao concluida (%d caracteres).", len(texto))
        return TranscriptionResult(texto=texto, idioma=idioma, backend="recognize_google")


class MockTranscriptionAdapter(TranscriptionPort):
    """
    Transcricao falsa para testes / execucao offline.

    Estrategia: se existir um arquivo de texto com o mesmo nome do audio
    (ex.: consulta.wav -> consulta.txt), usa o conteudo dele como "transcricao".
    Caso contrario devolve uma frase padrao. Nunca acessa a rede.
    """

    def __init__(self, texto_padrao: str = "transcricao simulada para teste") -> None:
        self.texto_padrao = texto_padrao

    def transcrever(self, caminho_wav: str, idioma: str = "pt-BR") -> TranscriptionResult:
        gemeo_txt = Path(caminho_wav).with_suffix(".txt")
        if gemeo_txt.exists():
            texto = gemeo_txt.read_text(encoding="utf-8").strip()
        else:
            texto = self.texto_padrao
        return TranscriptionResult(
            texto=texto, idioma=idioma, backend="mock", confianca=1.0
        )
