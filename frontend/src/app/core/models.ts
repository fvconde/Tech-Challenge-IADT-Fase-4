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

export interface DeteccaoVisual {
  classe: string; // classe COCO (knife, scissors, person, ...)
  confianca: number; // 0.0 a 1.0
  frame: number; // indice do frame (0 para imagem)
}

// Resposta unificada de TODOS os endpoints de analise.
export interface AnaliseRiscoResponse {
  transcricao: string | null;
  categorias_risco: CategoriaRisco[];
  sentimento: Sentimento;
  entidades: Entidade[];
  nivel_alerta: NivelAlerta;
  acao_recomendada: string;
  aviso: string;
  modalidades: string[]; // ex.: ["texto", "video", "laudo"]
  deteccoes_video: DeteccaoVisual[] | null;
  frames_analisados: number | null;
  imagem_anotada_b64: string | null; // JPEG (base64) com bounding boxes do YOLOv8
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
