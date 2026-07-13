import { Component, Input } from '@angular/core';
import { AnaliseRiscoResponse, CategoriaRisco } from '../core/models';
import { EmocaoVideoComponent } from './emocao-video.component';
import { NivelBadgeComponent } from './nivel-badge.component';

/**
 * Cartao que renderiza uma AnaliseRiscoResponse de QUALQUER modalidade.
 * Quando "destaque" e true (fusao) e o nivel e alto, mostra o banner de
 * "ALERTA A EQUIPE MEDICA". Usa o control flow nativo do Angular (@if/@for),
 * entao nao precisa do CommonModule.
 */
@Component({
  selector: 'app-alerta-card',
  standalone: true,
  imports: [NivelBadgeComponent, EmocaoVideoComponent],
  template: `
    <article
      class="card"
      [class.destaque]="destaque"
      [class.nivel-baixo]="resp.nivel_alerta === 'baixo'"
      [class.nivel-medio]="resp.nivel_alerta === 'medio'"
      [class.nivel-alto]="resp.nivel_alerta === 'alto'"
    >
      <header class="card-head">
        <div class="card-head-titulo">
          @if (destaque) { <span class="tele kicker">Alerta multimodal</span> }
          <h3>{{ titulo }}</h3>
        </div>
        <app-nivel-badge [nivel]="resp.nivel_alerta" />
      </header>

      <!-- Tira de corroboração: quais canais sustentam este alerta, num relance -->
      @if (destaque) {
        <div class="corrob">
          <span class="tele corrob-label">Corroboração</span>
          <div class="canais">
            <span class="canal" [class.on]="resp.modalidades.includes('texto')">Texto</span>
            <span class="canal" [class.on]="resp.modalidades.includes('audio')">Áudio</span>
            <span class="canal" [class.on]="resp.modalidades.includes('video')">Vídeo / imagem</span>
            <span class="canal" [class.on]="resp.modalidades.includes('pose')">Pose</span>
            <span class="canal" [class.on]="resp.modalidades.includes('emocao')">Emoção</span>
            <span class="canal" [class.on]="resp.modalidades.includes('laudo')">Laudo</span>
          </div>
          <span class="tele corrob-count">{{ resp.modalidades.length }} canais</span>
        </div>
      } @else if (resp.modalidades.length) {
        <div class="chips">
          <span class="tele rotulo">modalidades</span>
          @for (m of resp.modalidades; track m) { <span class="chip">{{ m }}</span> }
        </div>
      }

      @if (destaque && resp.nivel_alerta === 'alto') {
        <div class="alerta-equipe">
          <span class="alerta-icone" aria-hidden="true">▲</span>
          Alerta à equipe médica
        </div>
      }

      <div class="acao">
        <span class="tele rotulo">Ação recomendada</span>
        <p>{{ resp.acao_recomendada }}</p>
      </div>

      @if (categoriasVisiveis.length) {
        <div class="bloco">
          <span class="tele rotulo">Categorias de risco</span>
          <ul class="cats">
            @for (c of categoriasVisiveis; track c.categoria) {
              <li>
                <div class="cat-head">
                  <span class="cat-nome">{{ c.categoria }}</span>
                  <span
                    class="cat-score val"
                    [class.cs-baixo]="c.score < 0.3"
                    [class.cs-medio]="c.score >= 0.3 && c.score < 0.6"
                    [class.cs-alto]="c.score >= 0.6"
                    >{{ pct(c.score) }}</span>
                </div>
                @if (c.evidencias.length) {
                  <ul class="ev">
                    @for (e of c.evidencias; track e) { <li>{{ e }}</li> }
                  </ul>
                }
              </li>
            }
          </ul>
        </div>
      } @else if (!mostrarEmocao) {
        <p class="muted">Nenhuma categoria de risco identificada.</p>
      }

      <!-- Sinais emocionais no vídeo: o hexágono + vídeo anotado + timeline
           SUBSTITUEM a lista textual de "sinal_emocional_negativo" (filtrada
           acima) — o gráfico representa o mesmo indício de forma visual. -->
      @if (mostrarEmocao) {
        <div class="bloco emocao-bloco">
          <app-emocao-video [resp]="resp.emocao_video!" [embutido]="true" />
        </div>
      }

      <div class="grid">
        <div>
          <span class="tele rotulo">sentimento</span>
          {{ resp.sentimento.rotulo }} <span class="val">({{ pct(resp.sentimento.score) }})</span>
        </div>
        @if (resp.frames_analisados != null) {
          <div><span class="tele rotulo">frames analisados</span> <span class="val">{{ resp.frames_analisados }}</span></div>
        }
      </div>

      @if (resp.entidades.length) {
        <div class="chips">
          <span class="tele rotulo">entidades</span>
          @for (en of resp.entidades; track $index) {
            <span class="chip alt">{{ en.texto }} <em>{{ en.tipo }}</em></span>
          }
        </div>
      }

      @if (resp.transcricao) {
        <div class="bloco"><span class="tele rotulo">transcrição</span><p>{{ resp.transcricao }}</p></div>
      }
      @if (resp.resumo) {
        <div class="bloco"><span class="tele rotulo">resumo do laudo</span><p>{{ resp.resumo }}</p></div>
      }

      @if (resp.deteccoes_video?.length) {
        <div class="bloco">
          <span class="tele rotulo">detecções (vídeo)</span>
          <ul class="ev mono">
            @for (d of resp.deteccoes_video; track $index) {
              <li>{{ d.classe }} — conf {{ pct(d.confianca) }} (frame {{ d.frame }})</li>
            }
          </ul>
        </div>
      }

      @if (resp.imagem_anotada_b64) {
        <div class="bloco">
          <span class="tele rotulo">imagem anotada (YOLOv8)</span>
          <img
            class="anotada"
            [src]="'data:image/jpeg;base64,' + resp.imagem_anotada_b64"
            alt="Detecção YOLOv8 com bounding boxes"
          />
        </div>
      }

      @if (resp.texto_documento) {
        <details class="bloco">
          <summary>texto extraído do laudo</summary>
          <pre class="doc">{{ resp.texto_documento }}</pre>
        </details>
      }

      <footer class="card-foot">
        @if (destaque) {
          <span class="stamp-card">Apoio à decisão · não é diagnóstico</span>
        }
        <p class="aviso">{{ resp.aviso }}</p>
      </footer>
    </article>
  `,
  styles: [
    `
      /* ----- Card com "coluna de severidade" (spine) à esquerda ----- */
      .card {
        --sev: var(--sev-neutro);
        --sev-wash: #eef2f1;
        position: relative;
        background: var(--surface-raised);
        border: 1px solid var(--line);
        border-left: 5px solid var(--sev);
        border-radius: var(--radius);
        padding: 1.15rem 1.3rem;
        margin-bottom: 1.1rem;
        box-shadow: var(--shadow-card);
      }
      .card.nivel-baixo { --sev: var(--sev-baixo); --sev-wash: var(--sev-baixo-wash); }
      .card.nivel-medio { --sev: var(--sev-medio); --sev-wash: var(--sev-medio-wash); }
      .card.nivel-alto  { --sev: var(--sev-alto);  --sev-wash: var(--sev-alto-wash); }
      .card.destaque { border-left-width: 9px; padding: 1.4rem 1.5rem; }

      /* pulso único e discreto quando o alerta de fusão é ALTO */
      .card.destaque.nivel-alto { animation: alertaGlow 1.5s ease-out 2 both; }
      @keyframes alertaGlow {
        0%   { box-shadow: var(--shadow-card), 0 0 0 0 rgba(180, 35, 42, 0.34); }
        70%  { box-shadow: var(--shadow-card), 0 0 0 6px rgba(180, 35, 42, 0); }
        100% { box-shadow: var(--shadow-card); }
      }
      @media (prefers-reduced-motion: reduce) {
        .card.destaque.nivel-alto { animation: none; }
      }

      .card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
      .card-head-titulo { display: flex; flex-direction: column; gap: 0.25rem; }
      .kicker { color: var(--sev); }
      .card-head h3 {
        margin: 0;
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1.15rem;
        letter-spacing: -0.015em;
        color: var(--ink);
      }
      .card.destaque .card-head h3 { font-size: 1.4rem; }

      /* ----- Tira de corroboração (elemento-assinatura) ----- */
      .corrob {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem 0.8rem;
        margin: 0.9rem 0;
        padding: 0.7rem 0.85rem;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
      }
      .corrob-label { color: var(--ink-muted); }
      .canais { display: flex; flex-wrap: wrap; gap: 0.4rem; }
      .canal {
        font-family: var(--font-mono);
        font-size: 0.74rem;
        font-weight: 500;
        padding: 0.28rem 0.6rem;
        border-radius: var(--radius-pill);
        border: 1px solid var(--line);
        color: var(--ink-faint);
        background: var(--surface-raised);
        position: relative;
        transition: none;
      }
      /* canal que contribuiu: aceso na cor de severidade do alerta */
      .canal.on {
        color: var(--sev);
        border-color: var(--sev);
        background: var(--sev-wash);
        font-weight: 600;
      }
      .canal.on::before { content: '● '; font-size: 0.7em; }
      .canal:not(.on)::before { content: '○ '; font-size: 0.7em; }
      .corrob-count { color: var(--ink-muted); margin-left: auto; }

      /* ----- Banner de alerta à equipe (só fusão + alto) ----- */
      .alerta-equipe {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0.9rem 0;
        background: var(--sev-alto-wash);
        color: var(--sev-alto);
        border: 1px solid var(--sev-alto);
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: -0.01em;
        padding: 0.75rem 0.95rem;
        border-radius: var(--radius-sm);
      }
      .alerta-icone { font-size: 0.8em; }

      /* ----- Ação recomendada ----- */
      .acao {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
        padding: 0.7rem 0.9rem;
        margin: 0.8rem 0;
      }
      .acao p { margin: 0.35rem 0 0; color: var(--ink); }

      .bloco { margin: 0.85rem 0; }
      .bloco p { margin: 0.35rem 0 0; color: var(--ink); }
      .rotulo { display: inline-block; color: var(--ink-muted); margin-bottom: 0.15rem; }
      .grid { display: flex; flex-wrap: wrap; gap: 0.4rem 1.5rem; margin: 0.7rem 0; color: var(--ink); }
      .grid > div { display: flex; flex-direction: column; gap: 0.1rem; }
      .val { font-family: var(--font-mono); font-size: 0.9em; color: var(--ink); }

      /* ----- Chips (neutros: severidade é o único chroma) ----- */
      .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin: 0.7rem 0; }
      .chips .rotulo { margin-bottom: 0; margin-right: 0.2rem; }
      .chip {
        font-family: var(--font-mono);
        background: var(--surface-sunken);
        color: var(--ink);
        border-radius: var(--radius-pill);
        padding: 0.18rem 0.62rem;
        font-size: 0.76rem;
        font-weight: 500;
      }
      .chip.alt { background: var(--surface); border: 1px solid var(--line); }
      .chip em { color: var(--ink-muted); font-style: normal; margin-left: 0.25rem; }

      /* ----- Categorias de risco ----- */
      ul.cats { list-style: none; padding: 0; margin: 0.5rem 0 0; }
      ul.cats > li { padding: 0.55rem 0; border-top: 1px solid var(--line); }
      ul.cats > li:first-child { border-top: none; }
      .cat-head { display: flex; align-items: baseline; justify-content: space-between; gap: 0.75rem; }
      .cat-nome { font-weight: 600; color: var(--ink); }
      /* Cada score recebe a cor da SUA severidade (mesmos limiares do backend:
         >=0.6 alto, >=0.3 medio, senao baixo) — independe do nível do card,
         para o clínico distinguir indício forte de fraco num relance. */
      .cat-score {
        font-weight: 600;
        padding: 0.05rem 0.45rem;
        border-radius: var(--radius-pill);
        color: var(--ink-muted);
        background: var(--surface-sunken);
      }
      .cat-score.cs-baixo { color: var(--sev-baixo); background: var(--sev-baixo-wash); }
      .cat-score.cs-medio { color: var(--sev-medio); background: var(--sev-medio-wash); }
      .cat-score.cs-alto  { color: var(--sev-alto);  background: var(--sev-alto-wash); }
      ul.ev { margin: 0.35rem 0 0; padding-left: 1.15rem; color: var(--ink-muted); font-size: 0.88rem; }
      ul.ev.mono { font-family: var(--font-mono); font-size: 0.8rem; }
      ul.ev li { margin: 0.1rem 0; }

      .doc {
        white-space: pre-wrap;
        background: var(--chrome);
        color: var(--chrome-ink);
        font-family: var(--font-body);
        line-height: 1.55;
        padding: 0.8rem 0.9rem;
        border-radius: var(--radius-sm);
        font-size: 0.85rem;
        max-height: 240px;
        overflow: auto;
        /* scrollbar no tom petróleo, coerente com o trilho (Firefox) */
        scrollbar-width: thin;
        scrollbar-color: var(--chrome-line) transparent;
      }
      /* WebKit/Chromium */
      .doc::-webkit-scrollbar { width: 11px; height: 11px; }
      .doc::-webkit-scrollbar-track { background: transparent; }
      .doc::-webkit-scrollbar-thumb {
        background: var(--chrome-line);
        border-radius: var(--radius-pill);
        border: 3px solid var(--chrome);
      }
      .doc::-webkit-scrollbar-thumb:hover { background: var(--accent); }
      details.bloco summary {
        cursor: pointer;
        color: var(--accent);
        font-family: var(--font-mono);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }
      details.bloco[open] summary { margin-bottom: 0.5rem; }
      .anotada { display: block; max-width: 100%; border-radius: var(--radius-sm); border: 1px solid var(--line); margin-top: 0.45rem; }
      /* Separador sutil acima do painel de emoções embutido. */
      .emocao-bloco { border-top: 1px solid var(--line); padding-top: 0.85rem; }
      .muted { color: var(--ink-faint); font-style: italic; }

      /* ----- Rodapé + selo "não é diagnóstico" ----- */
      .card-foot {
        margin-top: 1rem;
        border-top: 1px solid var(--line);
        padding-top: 0.7rem;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.6rem;
      }
      .stamp-card {
        font-family: var(--font-mono);
        font-size: 0.64rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--ink-muted);
        border: 1px solid var(--line);
        border-radius: var(--radius-sm);
        padding: 0.28rem 0.5rem;
        line-height: 1.1;
      }
      .aviso { color: var(--ink-muted); font-size: 0.8rem; margin: 0; flex: 1; min-width: 12rem; }
    `,
  ],
})
export class AlertaCardComponent {
  @Input({ required: true }) resp!: AnaliseRiscoResponse;
  @Input() titulo = 'Resultado';
  @Input() destaque = false;

  /** Há painel de emoções (hexágono + vídeo anotado) para exibir dentro do alerta. */
  get mostrarEmocao(): boolean {
    return !!this.resp.emocao_video;
  }

  /**
   * Categorias mostradas como lista textual. Quando há o painel de emoções, a
   * categoria 'sinal_emocional_negativo' é OMITIDA — o hexágono a substitui
   * visualmente (pedido: "substitua a lista sinal_emocional_negativo pelo gráfico").
   */
  get categoriasVisiveis(): CategoriaRisco[] {
    if (!this.mostrarEmocao) return this.resp.categorias_risco;
    return this.resp.categorias_risco.filter(
      (c) => c.categoria !== 'sinal_emocional_negativo',
    );
  }

  pct(valor: number): string {
    return `${Math.round(valor * 100)}%`;
  }
}
