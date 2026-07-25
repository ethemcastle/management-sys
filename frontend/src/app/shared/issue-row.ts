import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { Issue } from '../core/models';
import { AvatarComponent } from './avatar';
import { BlockedPillComponent } from './blocked-pill';
import { LabelChipComponent } from './label-chip';
import { MondayBadgeComponent } from './monday-badge';
import { MondayStatusComponent } from './monday-status';
import { PriorityBarsComponent } from './priority-bars';
import { PrBadgeComponent } from './pr-badge';
import { TypeBadgeComponent } from './type-badge';

/** Dense list/backlog row. */
@Component({
  selector: 'app-issue-row',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    AvatarComponent,
    BlockedPillComponent,
    LabelChipComponent,
    MondayBadgeComponent,
    MondayStatusComponent,
    PriorityBarsComponent,
    PrBadgeComponent,
    TypeBadgeComponent,
  ],
  template: `
    @let i = issue();
    <div class="row" (click)="open.emit(i.key)">
      @if (showHandle()) {
        <span class="handle" (click)="$event.stopPropagation()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="9" cy="6" r="1.5" /><circle cx="15" cy="6" r="1.5" />
            <circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
            <circle cx="9" cy="18" r="1.5" /><circle cx="15" cy="18" r="1.5" />
          </svg>
        </span>
      }
      <app-type-badge [type]="i.type" [size]="18" />
      <span class="key">{{ i.key }}</span>
      <span class="title">{{ i.title }}</span>
      @if (i.mondayStatus) { <app-monday-status [label]="i.mondayStatus" [color]="i.mondayStatusColor ?? null" /> }
      @if (i.blocked) { <app-blocked-pill /> }
      <span class="labels">
        @for (l of i.labels; track l.name) { <app-label-chip [label]="l" /> }
      </span>
      <span class="spacer"></span>
      @if (i.mondayItemId) { <app-monday-badge [state]="i.syncState ?? 'synced'" /> }
      <app-priority-bars [priority]="i.priority" />
      <span class="pts">{{ i.points }}</span>
      <span class="prcol">
        @if (i.pr) { <app-pr-badge [pr]="i.pr" /> }
      </span>
      <app-avatar [member]="i.assignee" [size]="24" [rounded]="7" />
    </div>
  `,
  styles: [
    `
      .row {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 9px 14px;
        cursor: pointer;
        border-bottom: 1px solid var(--border);
        transition: background 0.12s ease;
      }
      .row:hover {
        background: var(--surface-2);
      }
      .handle {
        display: inline-flex;
        color: var(--text-3);
        cursor: grab;
        opacity: 0.6;
      }
      .handle:hover {
        opacity: 1;
      }
      .key {
        font-family: var(--font-mono);
        font-size: 11.5px;
        color: var(--text-3);
        font-weight: 500;
        flex-shrink: 0;
        width: 58px;
      }
      .title {
        font-size: 13.5px;
        font-weight: 500;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .labels {
        display: flex;
        gap: 5px;
        flex-shrink: 0;
      }
      .spacer {
        flex: 1;
      }
      .pts {
        font-family: var(--font-mono);
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-2);
        width: 18px;
        text-align: right;
        flex-shrink: 0;
      }
      .prcol {
        width: 62px;
        display: flex;
        justify-content: flex-start;
        flex-shrink: 0;
      }
    `,
  ],
})
export class IssueRowComponent {
  issue = input.required<Issue>();
  showHandle = input(true);
  open = output<string>();
}
