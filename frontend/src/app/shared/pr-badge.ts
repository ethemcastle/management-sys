import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { PullRequest } from '../core/models';
import { CiDotComponent } from './ci-dot';

@Component({
  selector: 'app-pr-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CiDotComponent],
  template: `
    <span class="pr">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="6" cy="6" r="2.4" />
        <circle cx="6" cy="18" r="2.4" />
        <circle cx="18" cy="7.5" r="2.4" />
        <path d="M6 8.4v7.2" />
        <path d="M18 10v2a4 4 0 0 1-4 4H8.4" />
      </svg>
      <span class="num">#{{ pr().num }}</span>
      <app-ci-dot [status]="pr().checks" />
    </span>
  `,
  styles: [
    `
      .pr {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: var(--text-3);
      }
      .num {
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 500;
        color: var(--text-2);
      }
    `,
  ],
})
export class PrBadgeComponent {
  pr = input.required<PullRequest>();
}
