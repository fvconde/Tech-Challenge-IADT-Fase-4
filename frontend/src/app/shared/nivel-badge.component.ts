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
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.05em;
        color: #fff;
        background: #64748b;
      }
      .baixo { background: #15803d; }
      .medio { background: #b45309; }
      .alto { background: #b91c1c; }
    `,
  ],
})
export class NivelBadgeComponent {
  @Input({ required: true }) nivel!: NivelAlerta;
}
