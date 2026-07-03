import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { ApiService } from '../core/api.service';
import { AnaliseRiscoResponse } from '../core/models';
import { AlertaCardComponent } from '../shared/alerta-card.component';

// Um item da lista de resultados mostrada na area central.
interface ResultadoItem {
  id: number;
  titulo: string;
  destaque: boolean; // true para a fusao (estilo "alerta a equipe")
  carregando: boolean;
  resp?: AnaliseRiscoResponse;
  erro?: string;
}

type TipoArquivo = 'audio' | 'video' | 'imagem' | 'laudo';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [FormsModule, AlertaCardComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent {
  private api = inject(ApiService);

  // entradas da sidebar
  texto = '';
  arquivos: Record<TipoArquivo, File | null> = {
    audio: null,
    video: null,
    imagem: null,
    laudo: null,
  };

  // feed de resultados (mais recente no topo)
  resultados = signal<ResultadoItem[]>([]);
  private contador = 0;

  // acoes em andamento (para o spinner/disabled por botao)
  private carregandoAcao = signal<Record<string, boolean>>({});
  carregando(acao: string): boolean {
    return this.carregandoAcao()[acao] === true;
  }
  private setCarregando(acao: string, valor: boolean): void {
    this.carregandoAcao.update((m) => ({ ...m, [acao]: valor }));
  }

  // relatos sinteticos de exemplo (sem PHI) para preencher o textarea rapidamente
  private readonly exemplos: Record<'posparto' | 'violencia' | 'rotina', string> = {
    posparto:
      'Desde que o bebê nasceu, há oito semanas, eu choro o dia todo sem motivo ' +
      'aparente e me sinto um fracasso como mãe. Não consigo dormir direito mesmo ' +
      'quando ele está dormindo, fico exausta o dia inteiro. Sinto uma ansiedade ' +
      'forte, com o coração acelerado, e às vezes um aperto no peito. Tenho ' +
      'vergonha de contar isso pra alguém.',
    violencia:
      'Meu marido não gosta que eu saia de casa sozinha e sempre pergunta onde ' +
      'estive e com quem falei. Nas últimas semanas ele tem levantado a voz e me ' +
      'chamado de incompetente na frente das crianças. Da última vez que ' +
      'discutimos ele apertou meu braço com força e ainda está com marca. Tenho ' +
      'medo da reação dele quando eu chegar em casa hoje.',
    rotina:
      'Vim para a consulta de acompanhamento de rotina do terceiro trimestre. ' +
      'Estou me sentindo bem, sem dores ou desconfortos incomuns. O bebê está ' +
      'mexendo normalmente e durmo razoavelmente bem. Só queria confirmar os ' +
      'exames de pressão e revisar a data provável do parto.',
  };

  carregarExemplo(tipo: 'posparto' | 'violencia' | 'rotina'): void {
    this.texto = this.exemplos[tipo];
  }

  // captura o arquivo escolhido em cada input
  onFile(ev: Event, tipo: TipoArquivo): void {
    const input = ev.target as HTMLInputElement;
    this.arquivos[tipo] = input.files && input.files.length ? input.files[0] : null;
  }

  // ---- acoes por modalidade ----
  analisarTexto(): void {
    if (!this.texto.trim()) {
      this.adicionarErro('Texto', 'Digite algum texto antes de analisar.');
      return;
    }
    this.executar('texto', 'Texto', false, this.api.analisarTexto(this.texto));
  }

  analisarAudio(): void {
    this.comArquivo('audio', 'Áudio', (f) => this.api.analisarAudio(f));
  }

  analisarVideo(): void {
    this.comArquivo('video', 'Vídeo', (f) => this.api.analisarVideo(f));
  }

  analisarImagem(): void {
    // imagem usa o mesmo endpoint de video (o backend aceita imagem)
    this.comArquivo('imagem', 'Imagem', (f) => this.api.analisarVideo(f));
  }

  analisarLaudo(): void {
    this.comArquivo('laudo', 'Laudo (PDF)', (f) => this.api.analisarLaudo(f));
  }

  // ---- fusao multimodal (tela principal da demo) ----
  fundir(): void {
    const video = this.arquivos.video ?? this.arquivos.imagem; // video tem prioridade
    const laudo = this.arquivos.laudo;
    if (!this.texto.trim() && !video && !laudo) {
      this.adicionarErro(
        '🚨 Alerta multimodal (fusão)',
        'Forneça ao menos uma modalidade: texto, vídeo/imagem e/ou laudo.',
      );
      return;
    }
    this.executar(
      'fusao',
      '🚨 Alerta multimodal (fusão)',
      true,
      this.api.analisarFusao({ texto: this.texto, video, laudo }),
    );
  }

  limpar(): void {
    this.resultados.set([]);
  }

  // ---- helpers ----
  private comArquivo(
    tipo: TipoArquivo,
    titulo: string,
    chamada: (f: File) => Observable<AnaliseRiscoResponse>,
  ): void {
    const file = this.arquivos[tipo];
    if (!file) {
      this.adicionarErro(titulo, `Selecione um arquivo de ${titulo.toLowerCase()} primeiro.`);
      return;
    }
    this.executar(tipo, titulo, false, chamada(file));
  }

  private executar(
    acao: string,
    titulo: string,
    destaque: boolean,
    chamada: Observable<AnaliseRiscoResponse>,
  ): void {
    const id = ++this.contador;
    this.setCarregando(acao, true);
    this.resultados.update((lista) => [
      { id, titulo, destaque, carregando: true },
      ...lista,
    ]);
    chamada.subscribe({
      next: (resp) => {
        this.setCarregando(acao, false);
        this.patch(id, { resp, carregando: false });
      },
      error: (err) => {
        this.setCarregando(acao, false);
        this.patch(id, { erro: this.msgErro(err), carregando: false });
      },
    });
  }

  private adicionarErro(titulo: string, erro: string): void {
    const id = ++this.contador;
    this.resultados.update((lista) => [
      { id, titulo, destaque: false, carregando: false, erro },
      ...lista,
    ]);
  }

  private patch(id: number, dados: Partial<ResultadoItem>): void {
    this.resultados.update((lista) =>
      lista.map((item) => (item.id === id ? { ...item, ...dados } : item)),
    );
  }

  private msgErro(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 0) {
        return 'Sem conexão com a API. O backend está rodando em http://127.0.0.1:8000? (CORS habilitado?)';
      }
      const detalhe = (err.error as { detail?: unknown })?.detail;
      if (typeof detalhe === 'string') return `Erro ${err.status}: ${detalhe}`;
      if (Array.isArray(detalhe)) {
        return `Erro ${err.status}: ${detalhe.map((d) => d?.msg ?? '').join('; ')}`;
      }
      return `Erro ${err.status}: ${err.message}`;
    }
    return 'Erro inesperado ao chamar a API.';
  }
}
