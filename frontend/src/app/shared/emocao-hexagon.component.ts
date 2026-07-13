import { Component, Input } from '@angular/core';
import { EmocaoPerfilItem } from '../core/models';

/**
 * Hexágono (radar) dos SINAIS EMOCIONAIS do vídeo.
 *
 * São 6 eixos = as 6 emoções do DeepFace sem 'happy' (a única positiva):
 * medo, tristeza, raiva, aversão, surpresa e neutro. O raio de cada eixo é a
 * intensidade média (0..1) daquela emoção nos frames em que houve rosto.
 *
 * Segue o sistema de design "triage console": a forma do perfil usa o petróleo
 * (accent, usado com parcimônia), os EIXOS NEGATIVOS são realçados na cor de
 * severidade (vermelho) e a grade fica recessiva. É uma série única, então não
 * precisa de legenda — o título já a nomeia.
 *
 * SVG inline (sem dependência de biblioteca de gráfico): geometria calculada no
 * TypeScript; responsivo via viewBox (largura 100%).
 */
interface EixoVM {
  label: string;
  negativa: boolean;
  valor: number;
  pct: string;
  vx: number; // vértice (ponta do dado)
  vy: number;
  lx: number; // posição do rótulo (fora do hexágono)
  ly: number;
  anchor: 'start' | 'middle' | 'end';
}

@Component({
  selector: 'app-emocao-hexagon',
  standalone: true,
  template: `
    <figure class="hex">
      <svg [attr.viewBox]="'0 0 ' + W + ' ' + H" role="img"
           [attr.aria-label]="rotuloAcessivel()">
        <!-- anéis da grade (0.25 · 0.5 · 0.75 · 1.0) -->
        @for (anel of aneis; track anel) {
          <polygon class="grid" [attr.points]="pontosNivel(anel)" />
        }
        <!-- raios (spokes) -->
        @for (e of eixos; track e.label) {
          <line class="spoke" [attr.x1]="cx" [attr.y1]="cy" [attr.x2]="e.vxMax" [attr.y2]="e.vyMax" />
        }
        <!-- polígono do perfil emocional -->
        <polygon class="area" [attr.points]="pontosDado()" />
        <!-- vértices -->
        @for (e of eixos; track e.label) {
          <circle
            class="dot"
            [class.neg]="e.negativa"
            [attr.cx]="e.vx"
            [attr.cy]="e.vy"
            r="3.5"
          />
        }
        <!-- rótulos (nome + %) -->
        @for (e of eixos; track e.label) {
          <text
            class="rot"
            [class.neg]="e.negativa"
            [attr.x]="e.lx"
            [attr.y]="e.ly"
            [attr.text-anchor]="e.anchor"
          >{{ e.label }}</text>
          <text
            class="pct"
            [attr.x]="e.lx"
            [attr.y]="e.ly + 12"
            [attr.text-anchor]="e.anchor"
          >{{ e.pct }}</text>
        }
      </svg>
    </figure>
  `,
  styles: [
    `
      .hex {
        margin: 0;
        width: 100%;
        max-width: 360px;
      }
      svg {
        width: 100%;
        height: auto;
        display: block;
        overflow: visible;
        font-family: var(--font-mono);
      }
      .grid {
        fill: none;
        stroke: var(--line);
        stroke-width: 1;
      }
      .spoke {
        stroke: var(--line);
        stroke-width: 1;
      }
      .area {
        fill: var(--accent);
        fill-opacity: 0.16;
        stroke: var(--accent);
        stroke-width: 2;
        stroke-linejoin: round;
      }
      .dot {
        fill: var(--accent);
      }
      .dot.neg {
        fill: var(--sev-alto);
      }
      .rot {
        font-size: 10.5px;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        fill: var(--ink-muted);
      }
      .rot.neg {
        fill: var(--sev-alto);
      }
      .pct {
        font-size: 10px;
        fill: var(--ink-faint);
      }
    `,
  ],
})
export class EmocaoHexagonComponent {
  // Dimensões do viewBox e do hexágono (espaço extra p/ os rótulos).
  readonly W = 340;
  readonly H = 300;
  readonly cx = 170;
  readonly cy = 148;
  readonly R = 92;
  readonly aneis = [0.25, 0.5, 0.75, 1];

  private _perfil: EmocaoPerfilItem[] = [];
  eixos: (EixoVM & { vxMax: number; vyMax: number })[] = [];

  @Input({ required: true }) set perfil(valor: EmocaoPerfilItem[]) {
    this._perfil = valor ?? [];
    this.recalcular();
  }
  get perfil(): EmocaoPerfilItem[] {
    return this._perfil;
  }

  // ângulo de cada eixo: começa no topo (-90°) e gira de 60 em 60 graus.
  private angulo(i: number): number {
    return (-90 + i * 60) * (Math.PI / 180);
  }

  private ponto(i: number, nivel: number): [number, number] {
    const a = this.angulo(i);
    return [this.cx + this.R * nivel * Math.cos(a), this.cy + this.R * nivel * Math.sin(a)];
  }

  private recalcular(): void {
    this.eixos = this._perfil.map((item, i) => {
      const a = this.angulo(i);
      const dx = Math.cos(a);
      const dy = Math.sin(a);
      const valor = Math.max(0, Math.min(1, item.valor));
      const [vx, vy] = this.ponto(i, valor);
      const [vxMax, vyMax] = this.ponto(i, 1);
      // rótulo posicionado logo além da ponta do eixo
      const lx = this.cx + (this.R + 16) * dx;
      const ly = this.cy + (this.R + 16) * dy;
      const anchor: 'start' | 'middle' | 'end' =
        Math.abs(dx) < 0.25 ? 'middle' : dx > 0 ? 'start' : 'end';
      return {
        label: item.emocao,
        negativa: item.negativa,
        valor,
        pct: `${Math.round(valor * 100)}%`,
        vx,
        vy,
        vxMax,
        vyMax,
        lx,
        ly,
        anchor,
      };
    });
  }

  pontosNivel(nivel: number): string {
    return this._perfil
      .map((_, i) => this.ponto(i, nivel).join(','))
      .join(' ');
  }

  pontosDado(): string {
    return this.eixos.map((e) => `${e.vx},${e.vy}`).join(' ');
  }

  rotuloAcessivel(): string {
    const partes = this._perfil.map((p) => `${p.emocao} ${Math.round(p.valor * 100)}%`);
    return `Perfil emocional (hexágono): ${partes.join(', ')}.`;
  }
}
