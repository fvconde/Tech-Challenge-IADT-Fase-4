import { Component, Input } from '@angular/core';
import { NivelAlerta } from '../core/models';

// Badge colorido de severidade: verde (baixo), ambar (medio), vermelho (alto).
@Component({
  selector: 'app-nivel-badge',
  standalone: true,
  template: `
    <span
      class="badge"
      [class.baixo]="nivel === 'baixo'"
      [class.medio]="nivel === 'medio'"
      [class.alto]="nivel === 'alto'"
    >{{ nivel }}</span>
  `,
  styles: [
    `
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.34rem;
        padding: 0.24rem 0.64rem 0.24rem 0.5rem;
        border-radius: var(--radius-pill, 999px);
        font-family: var(--font-mono, monospace);
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.7rem;
        letter-spacing: 0.09em;
        color: #fff;
        background: var(--sev-neutro, #7f9294);
      }
      /* ponto de triagem à esquerda do rótulo */
      .badge::before {
        content: '';
        width: 0.42rem;
        height: 0.42rem;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.9);
      }
      .baixo { background: var(--sev-baixo, #1f7a4d); }
      .medio { background: var(--sev-medio, #b0730c); }
      .alto { background: var(--sev-alto, #b4232a); }
    `,
  ],
})
export class NivelBadgeComponent {
  @Input({ required: true }) nivel!: NivelAlerta;
}
