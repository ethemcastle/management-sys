import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';

import { IssuesService } from '../../core/api/issues.service';
import { MondayStore } from '../../core/stores/monday.store';
import { Issue } from '../../core/models';
import { IssueRowComponent } from '../../shared/issue-row';

/** Category view: tickets filtered by a Product or Component value (from the
 *  sidebar category sections). Route: /category/:field/:value. */
@Component({
  selector: 'app-category',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IssueRowComponent],
  template: `
    <div class="view" style="max-width: 1180px;">
      <header class="chead">
        <div>
          <div class="eyebrow">{{ field() === 'product' ? 'Product' : 'Component' }}</div>
          <h1 class="h1">{{ value() }}</h1>
        </div>
        <span class="ccount">{{ issues().length }} {{ issues().length === 1 ? 'ticket' : 'tickets' }}</span>
      </header>

      @if (issues().length === 0) {
        <div class="empty-state">No tickets in this category.</div>
      } @else {
        <div class="card clist">
          @for (i of issues(); track i.key) {
            <app-issue-row [issue]="i" [showHandle]="false" (open)="go($event)" />
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      .chead {
        display: flex;
        align-items: flex-end;
        gap: 12px;
        margin-bottom: 18px;
      }
      .eyebrow {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-3);
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }
      .h1 {
        font-size: 22px;
        font-weight: 750;
        color: var(--text);
        letter-spacing: -0.01em;
        margin: 3px 0 0;
      }
      .ccount {
        margin-left: auto;
        font-size: 13px;
        color: var(--text-3);
      }
      .clist {
        padding: 6px;
        display: flex;
        flex-direction: column;
      }
      .empty-state {
        color: var(--text-3);
        padding: 44px;
        text-align: center;
      }
    `,
  ],
})
export class CategoryComponent {
  private issuesApi = inject(IssuesService);
  private monday = inject(MondayStore);
  private router = inject(Router);

  readonly field = input.required<string>();
  readonly value = input.required<string>();
  readonly issues = signal<Issue[]>([]);

  constructor() {
    effect(() => {
      this.monday.syncTick();
      const params = this.field() === 'product' ? { product: this.value() } : { component: this.value() };
      this.issuesApi.list(params).subscribe((list) => this.issues.set(list));
    });
  }

  go(key: string) {
    this.router.navigate(['/issues', key]);
  }
}
