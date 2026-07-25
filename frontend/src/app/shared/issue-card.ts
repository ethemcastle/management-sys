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

/** Kanban board card. Draggable styling is applied by the parent (cdkDrag). */
@Component({
  selector: 'app-issue-card',
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
    <div class="card" (click)="open.emit(i.key)">
      <div class="top">
        <app-type-badge [type]="i.type" />
        <span class="key">{{ i.key }}</span>
        @if (i.blocked) { <app-blocked-pill /> }
        <span class="sp"></span>
        @if (i.mondayItemId) { <app-monday-badge [state]="i.syncState ?? 'synced'" /> }
      </div>
      <div class="title">{{ i.title }}</div>
      @if (i.mondayStatus) {
        <div><app-monday-status [label]="i.mondayStatus" [color]="i.mondayStatusColor ?? null" /></div>
      }
      @if (i.labels.length) {
        <div class="labels">
          @for (l of i.labels; track l.name) { <app-label-chip [label]="l" /> }
        </div>
      }
      @if (i.pr) {
        <div class="prstrip">
          @if (i.pr.branch) { <span class="branch">{{ i.pr.branch }}</span> }
          <app-pr-badge [pr]="i.pr" />
        </div>
      }
      <div class="foot">
        <app-priority-bars [priority]="i.priority" />
        <span class="pts">{{ i.points }}</span>
        @if (i.commentCount) {
          <span class="cc" title="comments">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.38 8.38 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z" />
            </svg>
            {{ i.commentCount }}
          </span>
        }
        <span class="sp"></span>
        <app-avatar [member]="i.assignee" [size]="24" [rounded]="999" />
      </div>
    </div>
  `,
  styles: [
    `
      .card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 11px;
        padding: 11px 12px;
        display: flex;
        flex-direction: column;
        gap: 9px;
        box-shadow: var(--shadow-card);
        transition:
          border-color 0.15s ease,
          box-shadow 0.15s ease;
      }
      .card:hover {
        border-color: var(--border-2);
        box-shadow: var(--shadow-lift);
      }
      .top {
        display: flex;
        align-items: center;
        gap: 7px;
      }
      .key {
        font-family: var(--font-mono);
        font-size: 11.5px;
        color: var(--text-3);
        font-weight: 500;
      }
      .title {
        font-size: 13.5px;
        font-weight: 500;
        line-height: 1.4;
        color: var(--text);
      }
      .labels {
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
      }
      .prstrip {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 8px;
        background: var(--surface-2);
        border-radius: 7px;
        min-width: 0;
      }
      .branch {
        font-family: var(--font-mono);
        font-size: 10.5px;
        color: var(--text-3);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .foot {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .pts {
        font-family: var(--font-mono);
        font-size: 11.5px;
        font-weight: 600;
        color: var(--text-2);
      }
      .cc {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 11px;
        color: var(--text-3);
      }
      .sp {
        flex: 1;
      }
    `,
  ],
})
export class IssueCardComponent {
  issue = input.required<Issue>();
  open = output<string>();
}
