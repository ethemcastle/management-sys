import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { ViewsService } from '../../core/api/views.service';
import { Space, Timeline, TimelineRow } from '../../core/models';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayStore } from '../../core/stores/monday.store';

/**
 * Timeline / roadmap (Features space only). Renders a 12-week, 3-month grid with
 * one bar per Feature placed by startWeek/spanWeeks and filled by progress. The
 * Support space has no schedule, so it shows an empty state instead of the grid.
 */
@Component({
  selector: 'app-timeline',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="view">
      <header class="head">
        <div>
          <div class="eyebrow">Roadmap</div>
          <h1 class="h1">Timeline</h1>
        </div>
      </header>

      @let tl = data();
      @if (isEmpty()) {
        <div class="empty-state">Support work is triaged, not scheduled.</div>
      } @else if (tl) {
        <div class="card roadmap">
          <!-- Month header across the 12-week grid -->
          <div class="grid-head">
            <div class="lead"></div>
            <div class="months grid-bg">
              @for (m of tl.months; track m.label) {
                <div
                  class="month"
                  [style.left.%]="((m.startWeek - 1) / TOTAL_WEEKS) * 100"
                  [style.width.%]="(m.spanWeeks / TOTAL_WEEKS) * 100"
                >
                  {{ m.label }}
                </div>
              }
            </div>
          </div>

          <!-- Feature rows with a shared "Today" marker overlay -->
          <div class="rows">
            <!-- Overlay mirrors a row (lead + track) so the marker's % basis
                 matches the bars' % basis exactly. -->
            <div class="today-overlay">
              <div class="lead"></div>
              <div class="today-area">
                <div
                  class="today"
                  [style.left.%]="((tl.todayWeek - 0.5) / TOTAL_WEEKS) * 100"
                >
                  <span class="today-label">Today</span>
                </div>
              </div>
            </div>

            @for (row of tl.rows; track row.featureKey) {
              <div class="row">
                <button type="button" class="lead label" (click)="open(row.featureKey)">
                  <span class="dot" [style.background]="row.color"></span>
                  <span class="meta">
                    <span class="name">{{ row.name }}</span>
                    <span class="sub">{{ pct(row) }}% done</span>
                  </span>
                </button>

                <div class="track grid-bg" (click)="open(row.featureKey)">
                  <div
                    class="bar"
                    [style.left.%]="((row.startWeek - 1) / TOTAL_WEEKS) * 100"
                    [style.width.%]="(row.spanWeeks / TOTAL_WEEKS) * 100"
                    [style.background]="barBg(row.color)"
                    [style.borderColor]="barBorder(row.color)"
                    [title]="row.name + ' · ' + pct(row) + '% done'"
                  >
                    <div
                      class="fill"
                      [style.width.%]="row.progress * 100"
                      [style.background]="barFill(row.color)"
                    ></div>
                  </div>
                </div>
              </div>
            }
          </div>
        </div>

        <p class="legend micro">
          Bar length = scheduled span · filled portion = % complete. Click a feature to open it.
        </p>
      }
    </section>
  `,
  styles: [
    `
      .view {
        max-width: 1180px;
      }
      .head {
        margin-bottom: 18px;
      }
      .roadmap {
        padding: 6px 18px 18px;
        overflow: hidden;
      }

      /* Column geometry: fixed label lead + flexible week track. */
      .lead {
        width: 230px;
        flex: 0 0 230px;
      }

      /* Repeating vertical week gridlines behind the months + tracks. */
      .grid-bg {
        background-image: repeating-linear-gradient(
          90deg,
          var(--border) 0 1px,
          transparent 1px calc(100% / 12)
        );
      }

      .grid-head {
        display: flex;
        align-items: flex-end;
        height: 38px;
        border-bottom: 1px solid var(--border);
      }
      .months {
        position: relative;
        flex: 1;
        height: 100%;
      }
      .month {
        position: absolute;
        bottom: 8px;
        padding-left: 8px;
        font-size: 12px;
        font-weight: 700;
        color: var(--text-2);
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .rows {
        position: relative;
      }
      .row {
        display: flex;
        align-items: stretch;
        border-bottom: 1px solid var(--border);
      }
      .row:last-child {
        border-bottom: none;
      }

      /* "Today" overlay spans all rows; its track-area shares the bars' geometry. */
      .today-overlay {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        right: 0;
        display: flex;
        z-index: 2;
        pointer-events: none;
      }
      .today-area {
        position: relative;
        flex: 1;
        min-width: 0;
      }
      .today {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 0;
        transform: translateX(-1px);
        border-left: 2px solid var(--accent);
      }
      .today-label {
        position: absolute;
        top: 4px;
        left: 4px;
        font-size: 9.5px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--accent);
        background: var(--surface);
        padding: 1px 4px;
        border-radius: 5px;
        line-height: 1.4;
        white-space: nowrap;
      }

      .label {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 14px 12px 0;
        border: none;
        background: none;
        font-family: inherit;
        text-align: left;
        cursor: pointer;
        min-width: 0;
        color: var(--text);
        transition: color 0.15s ease;
      }
      .label:hover .name {
        color: var(--accent);
      }
      .dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        flex: 0 0 10px;
      }
      .meta {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .name {
        font-size: 13.5px;
        font-weight: 600;
        color: var(--text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        transition: color 0.15s ease;
      }
      .sub {
        font-size: 11.5px;
        font-weight: 500;
        color: var(--text-3);
      }

      .track {
        position: relative;
        flex: 1;
        min-width: 0;
        margin: 12px 0;
        cursor: pointer;
      }
      .bar {
        position: absolute;
        top: 0;
        bottom: 0;
        border: 1px solid transparent;
        border-radius: 7px;
        overflow: hidden;
        transition: filter 0.15s ease;
      }
      .track:hover .bar {
        filter: brightness(1.04);
      }
      .fill {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 0;
        border-radius: 6px 0 0 6px;
        transition: width 0.3s ease;
      }

      .legend {
        margin: 14px 2px 0;
        text-transform: none;
        letter-spacing: normal;
        font-weight: 500;
        font-size: 11.5px;
        color: var(--text-3);
      }
    `,
  ],
})
export class TimelineComponent {
  private views = inject(ViewsService);
  private router = inject(Router);
  private ws = inject(WorkspaceStore);
  private monday = inject(MondayStore);

  /** Weeks across the whole grid (3 months × 4). */
  protected readonly TOTAL_WEEKS = 12;

  protected readonly data = signal<Timeline | null>(null);

  /** No schedule to show for Support, or when the API returns an empty grid. */
  protected readonly isEmpty = computed(() => {
    if (this.ws.space() === 'support') return true;
    const tl = this.data();
    return !!tl && (tl.rows.length === 0 || tl.months.length === 0);
  });

  constructor() {
    effect(() => {
      const space = this.ws.space();
      this.monday.syncTick();
      this.load(space);
    });
  }

  private load(space: Space): void {
    // Skip the request for Support; the empty state covers it.
    if (space === 'support') {
      this.data.set(null);
      return;
    }
    this.views.timeline(space).subscribe((tl) => this.data.set(tl));
  }

  protected pct(row: TimelineRow): number {
    return Math.round(row.progress * 100);
  }

  protected barBg(color: string): string {
    return `color-mix(in oklab, ${color} 22%, transparent)`;
  }

  protected barBorder(color: string): string {
    return `color-mix(in oklab, ${color} 40%, transparent)`;
  }

  protected barFill(color: string): string {
    return `color-mix(in oklab, ${color} 55%, transparent)`;
  }

  protected open(featureKey: string): void {
    this.router.navigate(['/issues', featureKey]);
  }
}
