import { Component, Input } from '@angular/core';
import { AnaliseRiscoResponse } from '../core/models';
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
  imports: [NivelBadgeComponent],
  template: `
    <article class="card" [class.destaque]="destaque">
      <header class="card-head">
        <h3>{{ titulo }}</h3>
        <app-nivel-badge [nivel]="resp.nivel_alerta" />
      </header>

      @if (destaque && resp.nivel_alerta === 'alto') {
        <div class="alerta-equipe">🚨 ALERTA À EQUIPE MÉDICA</div>
      }

      @if (resp.modalidades.length) {
        <div class="chips">
          <span class="rotulo">modalidades:</span>
          @for (m of resp.modalidades; track m) { <span class="chip">{{ m }}</span> }
        </div>
      }

      <div class="acao">
        <strong>Ação recomendada</strong>
        <p>{{ resp.acao_recomendada }}</p>
      </div>

      @if (resp.categorias_risco.length) {
        <div class="bloco">
          <strong>Categorias de risco</strong>
          <ul class="cats">
            @for (c of resp.categorias_risco; track c.categoria) {
              <li>
                <span class="cat-nome">{{ c.categoria }}</span>
                <span class="cat-score">score {{ c.score.toFixed(2) }}</span>
                @if (c.evidencias.length) {
                  <ul class="ev">
                    @for (e of c.evidencias; track e) { <li>{{ e }}</li> }
                  </ul>
                }
              </li>
            }
          </ul>
        </div>
      } @else {
        <p class="muted">Nenhuma categoria de risco identificada.</p>
      }

      <div class="grid">
        <div>
          <span class="rotulo">sentimento</span>
          {{ resp.sentimento.rotulo }} ({{ resp.sentimento.score.toFixed(2) }})
        </div>
        @if (resp.frames_analisados != null) {
          <div><span class="rotulo">frames analisados</span> {{ resp.frames_analisados }}</div>
        }
      </div>

      @if (resp.entidades.length) {
        <div class="chips">
          <span class="rotulo">entidades:</span>
          @for (en of resp.entidades; track $index) {
            <span class="chip alt">{{ en.texto }} <em>({{ en.tipo }})</em></span>
          }
        </div>
      }

      @if (resp.transcricao) {
        <div class="bloco"><span class="rotulo">transcrição</span><p>{{ resp.transcricao }}</p></div>
      }
      @if (resp.resumo) {
        <div class="bloco"><span class="rotulo">resumo do laudo</span><p>{{ resp.resumo }}</p></div>
      }

      @if (resp.deteccoes_video?.length) {
        <div class="bloco">
          <span class="rotulo">detecções (vídeo)</span>
          <ul class="ev">
            @for (d of resp.deteccoes_video; track $index) {
              <li>{{ d.classe }} — conf {{ d.confianca.toFixed(2) }} (frame {{ d.frame }})</li>
            }
          </ul>
        </div>
      }

      @if (resp.imagem_anotada_b64) {
        <div class="bloco">
          <span class="rotulo">imagem anotada (YOLOv8)</span>
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
        <p class="aviso">⚠️ {{ resp.aviso }}</p>
      </footer>
    </article>
  `,
  styles: [
    `
      .card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-left: 6px solid #94a3b8;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
      }
      .card.destaque { border-left-color: #b91c1c; border-width: 1px 1px 1px 8px; }
      .card-head { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
      .card-head h3 { margin: 0; font-size: 1.05rem; }
      .alerta-equipe {
        margin: 0.6rem 0;
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fecaca;
        font-weight: 800;
        letter-spacing: 0.03em;
        padding: 0.6rem 0.8rem;
        border-radius: 8px;
        text-align: center;
      }
      .acao { background: #f1f5f9; border-radius: 8px; padding: 0.6rem 0.8rem; margin: 0.7rem 0; }
      .acao p { margin: 0.3rem 0 0; }
      .bloco { margin: 0.7rem 0; }
      .rotulo { color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; margin-right: 0.3rem; }
      .grid { display: flex; flex-wrap: wrap; gap: 1.2rem; margin: 0.5rem 0; }
      .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin: 0.5rem 0; }
      .chip { background: #e0e7ff; color: #3730a3; border-radius: 999px; padding: 0.15rem 0.6rem; font-size: 0.8rem; font-weight: 600; }
      .chip.alt { background: #ecfeff; color: #155e75; }
      .chip em { color: #64748b; font-style: normal; }
      ul.cats { list-style: none; padding: 0; margin: 0.4rem 0 0; }
      ul.cats > li { padding: 0.4rem 0; border-top: 1px dashed #e2e8f0; }
      .cat-nome { font-weight: 700; }
      .cat-score { color: #64748b; margin-left: 0.5rem; font-size: 0.85rem; }
      ul.ev { margin: 0.3rem 0 0; padding-left: 1.1rem; color: #475569; font-size: 0.88rem; }
      .doc { white-space: pre-wrap; background: #0f172a; color: #e2e8f0; padding: 0.7rem; border-radius: 8px; font-size: 0.8rem; max-height: 240px; overflow: auto; }
      .anotada { display: block; max-width: 100%; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 0.4rem; }
      .muted { color: #94a3b8; font-style: italic; }
      .card-foot { margin-top: 0.8rem; border-top: 1px solid #f1f5f9; padding-top: 0.5rem; }
      .aviso { color: #92400e; font-size: 0.82rem; margin: 0; }
    `,
  ],
})
export class AlertaCardComponent {
  @Input({ required: true }) resp!: AnaliseRiscoResponse;
  @Input() titulo = 'Resultado';
  @Input() destaque = false;
}
