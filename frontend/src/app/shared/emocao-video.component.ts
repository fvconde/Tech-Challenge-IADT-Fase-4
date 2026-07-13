import { Component, Input, inject } from '@angular/core';
import { ApiService } from '../core/api.service';
import { EmocaoVideoPanel } from '../core/models';
import { EmocaoHexagonComponent } from './emocao-hexagon.component';

/**
 * Painel de EMOÇÕES do vídeo: mostra o vídeo anotado (rosto + emoção por frame,
 * desenhados no backend com cv2), o HEXÁGONO dos sinais emocionais e a faixa por
 * frame (timeline). É o bloco `emocao_video` de POST /api/video/analyze.
 *
 * Postura ética: NÃO é diagnóstico — sinaliza para a equipe avaliar.
 */
@Component({
  selector: 'app-emocao-video',
  standalone: true,
  imports: [EmocaoHexagonComponent],
  template: `
    <article class="card" [class.embutido]="embutido">
      <header class="card-head">
        <div>
          @if (embutido) {
            <span class="tele kicker">Sinais emocionais no vídeo · DeepFace</span>
          } @else {
            <span class="tele kicker">Emoções no vídeo · DeepFace</span>
            <h3>Sinais emocionais detectados por frame</h3>
          }
        </div>
        <div class="dominante" [class.neg]="dominanteNegativa()">
          <span class="emoji" aria-hidden="true">{{ emojiDe(resp.dominante_geral) }}</span>
          <div>
            <span class="tele rotulo">dominante</span>
            <strong>{{ resp.dominante_geral }}</strong>
          </div>
        </div>
      </header>

      <div class="grade">
        <!-- Vídeo anotado (rosto + emoção desenhados a cada frame) -->
        <div class="video-box">
          <span class="tele rotulo">vídeo anotado (rosto + emoção)</span>
          @if (resp.frames_com_rosto > 0) {
            <video controls preload="metadata" [src]="src()" playsinline>
              Seu navegador não reproduz este vídeo (MP4/H.264).
            </video>
          } @else {
            <p class="muted">
              Nenhum rosto foi detectado neste vídeo — não há emoções para anotar.
            </p>
          }
          <div class="meta">
            <span><span class="tele rotulo">frames</span> {{ resp.frames_total }}</span>
            <span><span class="tele rotulo">com rosto</span> {{ resp.frames_com_rosto }}</span>
            <span><span class="tele rotulo">amostrados</span> {{ resp.frames_analisados }}</span>
            <span><span class="tele rotulo">fps</span> {{ resp.fps }}</span>
          </div>
        </div>

        <!-- Hexágono dos sinais emocionais -->
        <div class="hex-box">
          <span class="tele rotulo">perfil emocional (hexágono)</span>
          <app-emocao-hexagon [perfil]="resp.perfil" />
          <p class="legenda">
            <span class="pt neg">■</span> valência negativa (risco)
            <span class="pt pos">■</span> neutra / surpresa
          </p>
        </div>
      </div>

      <!-- Faixa por frame (timeline) -->
      @if (resp.timeline.length) {
        <div class="tl-box">
          <span class="tele rotulo">emoção por frame amostrado</span>
          <div class="tl">
            @for (f of resp.timeline; track f.frame) {
              <div class="tl-item" [class.neg]="negativa(f.emocao)" [title]="f.emocao + ' · ' + pct(f.score)">
                <span class="tl-emo">{{ f.emocao }}</span>
                <span class="tl-t">{{ f.tempo_s }}s</span>
              </div>
            }
          </div>
        </div>
      }
    </article>
  `,
  styles: [
    `
      .card {
        position: relative;
        background: var(--surface-raised);
        border: 1px solid var(--line);
        border-left: 5px solid var(--accent);
        border-radius: var(--radius);
        padding: 1.2rem 1.35rem;
        margin-bottom: 1.1rem;
        box-shadow: var(--shadow-card);
      }
      /* Modo "embutido": some com a moldura de card (borda/sombra/padding) para
         a seção viver DENTRO de outro card (o alerta multimodal). */
      .card.embutido {
        background: transparent;
        border: none;
        border-radius: 0;
        box-shadow: none;
        padding: 0;
        margin: 0;
      }
      .card-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
      }
      .kicker {
        color: var(--accent);
      }
      .card-head h3 {
        margin: 0.25rem 0 0;
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1.2rem;
        letter-spacing: -0.015em;
        color: var(--ink);
      }
      .dominante {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
        padding: 0.45rem 0.7rem;
        background: var(--surface);
      }
      .dominante.neg {
        border-color: var(--sev-alto);
        background: var(--sev-alto-wash);
      }
      .dominante strong {
        display: block;
        text-transform: capitalize;
        color: var(--ink);
      }
      .dominante.neg strong {
        color: var(--sev-alto);
      }
      .emoji {
        font-size: 1.5rem;
        line-height: 1;
      }

      .grade {
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        gap: 1.2rem;
        margin: 1rem 0;
        align-items: start;
      }
      @media (max-width: 720px) {
        .grade {
          grid-template-columns: 1fr;
        }
      }
      .rotulo {
        display: block;
        color: var(--ink-muted);
        margin-bottom: 0.35rem;
      }
      video {
        width: 100%;
        border-radius: var(--radius-sm);
        border: 1px solid var(--line);
        background: #000;
        display: block;
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.3rem 1.1rem;
        margin-top: 0.55rem;
        font-family: var(--font-mono);
        font-size: 0.82rem;
        color: var(--ink);
      }
      .meta .rotulo {
        display: inline;
        margin: 0 0.25rem 0 0;
      }

      .hex-box {
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .legenda {
        margin: 0.4rem 0 0;
        font-family: var(--font-mono);
        font-size: 0.72rem;
        color: var(--ink-muted);
        display: flex;
        gap: 0.8rem;
        align-items: center;
      }
      .pt {
        margin-right: 0.2rem;
      }
      .pt.neg {
        color: var(--sev-alto);
      }
      .pt.pos {
        color: var(--accent);
      }

      .tl-box {
        margin-top: 0.4rem;
      }
      .tl {
        display: flex;
        gap: 0.4rem;
        overflow-x: auto;
        padding-bottom: 0.4rem;
        scrollbar-width: thin;
        scrollbar-color: var(--line) transparent;
      }
      .tl-item {
        flex: 0 0 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.15rem;
        min-width: 3.6rem;
        padding: 0.4rem 0.5rem;
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
        background: var(--surface);
      }
      .tl-item.neg {
        border-color: var(--sev-alto);
        background: var(--sev-alto-wash);
      }
      .tl-emo {
        font-family: var(--font-mono);
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: capitalize;
        color: var(--ink);
      }
      .tl-item.neg .tl-emo {
        color: var(--sev-alto);
      }
      .tl-t {
        font-family: var(--font-mono);
        font-size: 0.68rem;
        color: var(--ink-muted);
      }

      .muted {
        color: var(--ink-faint);
        font-style: italic;
      }
    `,
  ],
})
export class EmocaoVideoComponent {
  private api = inject(ApiService);
  @Input({ required: true }) resp!: EmocaoVideoPanel;
  // Quando true, renderiza como SEÇÃO dentro de outro card (sem moldura/rodapé
  // próprios e com cabeçalho mais discreto). Usado pelo alerta multimodal.
  @Input() embutido = false;

  // emoções de valência negativa (destacadas em vermelho)
  private readonly negativas = new Set(['medo', 'tristeza', 'raiva', 'aversão']);
  private readonly emojis: Record<string, string> = {
    medo: '😨',
    tristeza: '😢',
    raiva: '😠',
    aversão: '🤢',
    surpresa: '😲',
    neutro: '😐',
    alegria: '🙂',
  };

  src(): string {
    return this.api.urlVideoAnotado(this.resp.video_url);
  }
  emojiDe(emocao: string): string {
    return this.emojis[emocao] ?? '🙂';
  }
  negativa(emocao: string): boolean {
    return this.negativas.has(emocao);
  }
  dominanteNegativa(): boolean {
    return this.negativa(this.resp.dominante_geral);
  }
  pct(score: number): string {
    return `${Math.round(score * 100)}%`;
  }
}
