import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { ActionItem, ActionType } from '../core/models';
import { CiDotComponent } from './ci-dot';
import { MondayStatusComponent } from './monday-status';
import { TypeBadgeComponent } from './type-badge';

interface KindMeta {
  label: string; // the chip label
  color: string; // chip/dot colour
  action: string; // primary button label
}
const KIND: Record<ActionType, KindMeta> = {
  ci_failing: { label: 'CI failing', color: 'var(--danger)', action: 'View' },
  changes_requested: { label: 'Changes', color: 'var(--ai)', action: 'Address' },
  review_request: { label: 'Review', color: 'var(--accent)', action: 'Review' },
  blocked: { label: 'Blocked', color: 'var(--danger)', action: 'Unblock' },
  monday_unsynced: { label: 'monday', color: 'var(--warning)', action: 'Sync' },
};

/** One row in the developer "Needs you" queue: kind chip + ticket + inline
 *  code/sync signal + ONE primary action. Row click opens the ticket. */
@Component({
  selector: 'app-action-row',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CiDotComponent, MondayStatusComponent, TypeBadgeComponent],
  template: `
    @let a = item();
    @let i = a.issue;
    <div class="arow" (click)="open.emit(i.key)">
      <span class="chip" [style.background]="meta().color + '1f'" [style.color]="meta().color">
        <span class="cdot" [style.background]="meta().color"></span>{{ meta().label }}
      </span>
      <app-type-badge [type]="i.type" [size]="16" />
      <span class="key">{{ i.key }}</span>
      <span class="title">{{ i.title }}</span>
      <span class="spacer"></span>
      @if (i.mondayStatus) { <app-monday-status [label]="i.mondayStatus" [color]="i.mondayStatusColor ?? null" /> }
      @if (i.pr) {
        <span class="pr"><span class="mono">#{{ i.pr.num }}</span><app-ci-dot [status]="i.pr.checks" /></span>
      }
      <div class="acts" (click)="$event.stopPropagation()">
        @if (a.kind === 'blocked') {
          <button class="btn-mini primary" (click)="unblock.emit(i.key)">Unblock</button>
          <button class="btn-mini" (click)="open.emit(i.key)">Open</button>
        } @else if (a.kind === 'monday_unsynced') {
          <button class="btn-mini primary" (click)="sync.emit()">Sync</button>
        } @else {
          <button class="btn-mini primary" (click)="open.emit(i.key)">{{ meta().action }}</button>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .arow {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 9px 4px;
        border-top: 1px solid var(--border);
        cursor: pointer;
      }
      .arow:first-child {
        border-top: none;
      }
      .arow:hover {
        background: var(--surface-2);
      }
      .chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 10.5px;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        white-space: nowrap;
        flex: none;
        width: 92px;
      }
      .cdot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        flex: none;
      }
      .key {
        font-family: var(--font-mono);
        font-size: 11.5px;
        color: var(--text-3);
        font-weight: 500;
        flex: none;
      }
      .title {
        font-size: 13px;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .spacer {
        flex: 1;
      }
      .pr {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        flex: none;
      }
      .mono {
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--text-3);
      }
      .acts {
        display: inline-flex;
        gap: 6px;
        flex: none;
      }
      .btn-mini {
        font-size: 12px;
        font-weight: 600;
        font-family: inherit;
        padding: 5px 11px;
        border-radius: 7px;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text-2);
        cursor: pointer;
        white-space: nowrap;
      }
      .btn-mini:hover {
        border-color: var(--border-2);
        color: var(--text);
      }
      .btn-mini.primary {
        border-color: var(--accent-line);
        background: var(--accent-soft);
        color: var(--accent);
      }
    `,
  ],
})
export class ActionRowComponent {
  readonly item = input.required<ActionItem>();
  readonly open = output<string>();
  readonly unblock = output<string>();
  readonly sync = output<void>();

  readonly meta = computed(() => KIND[this.item().kind]);
}
