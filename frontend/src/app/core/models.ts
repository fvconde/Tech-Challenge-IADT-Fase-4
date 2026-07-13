// Tipos TypeScript que ESPELHAM os schemas Pydantic do backend
// (backend/app/models/schemas.py). Mantenha em sincronia com o backend.

export type NivelAlerta = 'baixo' | 'medio' | 'alto';

export interface Sentimento {
  rotulo: string; // positivo | neutro | negativo
  score: number; // -1.0 a +1.0
  backend: string;
}

export interface Entidade {
  texto: string;
  tipo: string; // sintoma | medicamento | tempo | ...
}

export interface CategoriaRisco {
  categoria: string; // ex.: depressao_pos_parto, violencia_domestica, ...
  score: number; // 0.0 a 1.0
  evidencias: string[]; // trechos/termos/deteccoes que motivaram o indicio
}

// Categorizacao por TRECHO (chunk): qual frase motivou o indicio, de qual fonte.
// Complementa CategoriaRisco (agregado) com rastreabilidade fina.
export interface Achado {
  fonte: string; // texto | audio | laudo | video | pose | emocao
  trecho: string; // frase que motivou o indicio
  categoria: string; // categoria de risco detectada nesse trecho
  score: number; // 0.0 a 1.0
  metadados: Record<string, unknown>; // ex.: { indice_trecho: 2 }
}

export interface DeteccaoVisual {
  classe: string; // classe COCO (knife, scissors, person, ...)
  confianca: number; // 0.0 a 1.0
  frame: number; // indice do frame (0 para imagem)
}

// Resposta unificada de TODOS os endpoints de analise.
export interface AnaliseRiscoResponse {
  transcricao: string | null;
  categorias_risco: CategoriaRisco[];
  achados: Achado[]; // categorizacao por trecho (rastreabilidade fina)
  sentimento: Sentimento;
  entidades: Entidade[];
  nivel_alerta: NivelAlerta;
  acao_recomendada: string;
  aviso: string;
  modalidades: string[]; // ex.: ["texto", "video", "laudo"]
  deteccoes_video: DeteccaoVisual[] | null;
  frames_analisados: number | null;
  imagem_anotada_b64: string | null; // JPEG (base64) com bounding boxes do YOLOv8
  emocao_video: EmocaoVideoPanel | null; // hexágono + vídeo anotado (quando há vídeo + DeepFace)
  texto_documento: string | null;
  resumo: string | null;
  backend_transcricao: string | null;
  backend_nlp: string | null;
  backend_video: string | null;
  backend_ocr: string | null;
  backend_summarizer: string | null;
}

// Resposta de GET /api/video/status
export interface VideoStatus {
  modulo: string;
  backend: string;
  modelo: string;
  classes_foco: string[];
  amostragem_frames: number;
}

// ---- Painel de emoções no vídeo (hexágono + vídeo anotado) ----
// Espelha EmocaoVideoPanel do backend, embutido em AnaliseRiscoResponse.emocao_video.

export interface EmocaoPerfilItem {
  emocao: string; // rótulo PT (eixo do hexágono): medo, tristeza, raiva, aversão...
  valor: number; // 0.0 a 1.0 (intensidade média nos frames com rosto)
  negativa: boolean; // true para emoções de valência negativa
}

export interface EmocaoFrameItem {
  frame: number;
  tempo_s: number;
  emocao: string; // emoção dominante do frame (PT)
  score: number; // 0.0 a 1.0
}

export interface EmocaoVideoPanel {
  video_id: string;
  video_url: string; // caminho relativo p/ baixar/reproduzir o vídeo anotado (MP4)
  perfil: EmocaoPerfilItem[]; // os 6 eixos do hexágono
  timeline: EmocaoFrameItem[]; // emoção dominante por frame amostrado
  frames_analisados: number;
  frames_total: number;
  frames_com_rosto: number;
  fps: number;
  dominante_geral: string;
  backend: string;
}
