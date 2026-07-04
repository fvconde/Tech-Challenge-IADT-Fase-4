import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from './api-config';
import { AnaliseRiscoResponse, VideoStatus } from './models';

// Entrada da fusao multimodal: qualquer combinacao das modalidades.
export interface FusaoInput {
  texto?: string;
  audio?: File | null; // WAV/FLAC (transcrito -> NLP)
  video?: File | null; // video OU imagem
  imagem?: File | null; // imagem adicional (combinada com o video, nao descartada)
  laudo?: File | null; // PDF
}

/**
 * Service HTTP tipado que cobre TODOS os endpoints da API.
 * Cada metodo devolve um Observable<AnaliseRiscoResponse> (ou VideoStatus).
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = API_BASE_URL;

  // POST /api/text/analyze  (JSON)
  analisarTexto(texto: string): Observable<AnaliseRiscoResponse> {
    return this.http.post<AnaliseRiscoResponse>(`${this.base}/api/text/analyze`, { texto });
  }

  // POST /api/audio/analyze  (multipart, campo "arquivo" - WAV)
  analisarAudio(file: File): Observable<AnaliseRiscoResponse> {
    return this.http.post<AnaliseRiscoResponse>(
      `${this.base}/api/audio/analyze`,
      this.form('arquivo', file),
    );
  }

  // POST /api/video/analyze  (multipart, campo "arquivo" - video OU imagem)
  analisarVideo(file: File): Observable<AnaliseRiscoResponse> {
    return this.http.post<AnaliseRiscoResponse>(
      `${this.base}/api/video/analyze`,
      this.form('arquivo', file),
    );
  }

  // POST /api/laudo/analyze  (multipart, campo "arquivo" - PDF)
  analisarLaudo(file: File): Observable<AnaliseRiscoResponse> {
    return this.http.post<AnaliseRiscoResponse>(
      `${this.base}/api/laudo/analyze`,
      this.form('arquivo', file),
    );
  }

  // POST /api/fusion/analyze  (multipart: texto + audio + video + imagem + laudo)
  analisarFusao(input: FusaoInput): Observable<AnaliseRiscoResponse> {
    const fd = new FormData();
    if (input.texto && input.texto.trim()) fd.append('texto', input.texto);
    if (input.audio) fd.append('audio_arquivo', input.audio);
    if (input.video) fd.append('video_arquivo', input.video);
    if (input.imagem) fd.append('imagem_arquivo', input.imagem);
    if (input.laudo) fd.append('laudo_arquivo', input.laudo);
    return this.http.post<AnaliseRiscoResponse>(`${this.base}/api/fusion/analyze`, fd);
  }

  // GET /api/video/status
  videoStatus(): Observable<VideoStatus> {
    return this.http.get<VideoStatus>(`${this.base}/api/video/status`);
  }

  // monta um FormData de um unico arquivo
  private form(campo: string, file: File): FormData {
    const fd = new FormData();
    fd.append(campo, file);
    return fd;
  }
}
