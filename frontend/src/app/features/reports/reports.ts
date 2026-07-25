import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';

import { ViewsService } from '../../core/api/views.service';
import { Reports, Space } from '../../core/models';
import { STATUS_META } from '../../core/theme';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayStore } from '../../core/stores/monday.store';

/** Geometry for the burndown SVG, precomputed so the template stays declarative. */
interface BurndownGeom {
  vbW: number;
  vbH: number;
  innerW: number;
  chartH: number;
  padL: number;
  padT: number;
  /** Polyline "x,y ..." point strings. */
  idealPts: string;
  actualPts: string;
  /** Closed area path under the actual line, down to the baseline. */
  areaPath: string;
  baseY: number;
  /** Vertical "Today" marker x (in viewBox units). */
  todayX: number;
  yLabels: { text: string; y: number }[];
  xLabels: { text: string; x: number }[];
  /** Hover markers on the actual line (one per elapsed day). */
  actualDots: { x: number; y: number; label: string }[];
}

/** A single grouped column in the velocity chart, with heights as percentages. */
interface VelocityCol {
  sprint: string;
  committedPct: number;
  completedPct: number;
  committed: number;
  completed: number;
}

/** One segment (and its legend entry) of the work-distribution bar. */
interface DistSeg {
  status: string;
  label: string;
  count: number;
  color: string;
  widthPct: number;
}

/** Reports & analytics: stat cards, burndown, velocity, and distribution. */
@Component({
  selector: 'app-reports',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="view" style="max-width: 1180px;">
      <header class="head">
        <div>
          <div class="eyebrow">Insights · {{ spaceName() }}</div>
          <h1 class="h1">Reports &amp; analytics</h1>
        </div>
      </header>

      @if (data(); as r) {
        <!-- 1. Stat cards -->
        <section class="stats">
          @for (s of r.stats; track s.label) {
            <div class="card card-pad stat">
              <div class="stat-label">{{ s.label }}</div>
              <div class="stat-value">
                <span class="stat-num mono">{{ s.value }}</span>
                @if (s.unit) { <span class="stat-unit">{{ s.unit }}</span> }
              </div>
              <div class="stat-delta" [class.bad]="!s.good">{{ s.delta }}</div>
            </div>
          }
        </section>

        <!-- 2. Sprint burndown -->
        <section class="card card-pad chart-card">
          <div class="sec-head">
            <span class="sec-title">Sprint burndown</span>
            <span class="chart-sub">Remaining work vs. ideal pace</span>
          </div>

          @if (burndown(); as b) {
            <svg
              class="burndown"
              [attr.viewBox]="'0 0 ' + b.vbW + ' ' + b.vbH"
              width="100%"
              preserveAspectRatio="none"
              role="img"
              aria-label="Sprint burndown chart"
            >
              <!-- gridlines at each y-axis tick -->
              @for (yl of b.yLabels; track yl.text) {
                <line
                  [attr.x1]="b.padL"
                  [attr.y1]="yl.y"
                  [attr.x2]="b.padL + b.innerW"
                  [attr.y2]="yl.y"
                  stroke="var(--border)"
                  stroke-width="1"
                />
              }

              <!-- soft area fill under the actual line -->
              <path [attr.d]="b.areaPath" fill="var(--accent-soft)" stroke="none" />

              <!-- ideal (dashed) -->
              <polyline
                [attr.points]="b.idealPts"
                fill="none"
                stroke="var(--text-3)"
                stroke-width="1.5"
                stroke-dasharray="4 4"
                stroke-linejoin="round"
              />

              <!-- actual (solid accent) -->
              <polyline
                [attr.points]="b.actualPts"
                fill="none"
                stroke="var(--accent)"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />

              <!-- actual data points (hover for the remaining value) -->
              @for (d of b.actualDots; track d.x) {
                <circle
                  [attr.cx]="d.x"
                  [attr.cy]="d.y"
                  r="2.6"
                  fill="var(--accent)"
                  stroke="var(--surface)"
                  stroke-width="1"
                >
                  <title>{{ d.label }}</title>
                </circle>
              }

              <!-- today marker -->
              <line
                [attr.x1]="b.todayX"
                [attr.y1]="b.padT"
                [attr.x2]="b.todayX"
                [attr.y2]="b.baseY"
                stroke="var(--text-3)"
                stroke-width="1"
                stroke-dasharray="3 3"
              />
              <text
                [attr.x]="b.todayX + 4"
                [attr.y]="b.padT + 9"
                class="svg-label"
                fill="var(--text-3)"
              >
                Today
              </text>

              <!-- y-axis labels -->
              @for (yl of b.yLabels; track yl.text) {
                <text
                  [attr.x]="b.padL - 6"
                  [attr.y]="yl.y + 3"
                  text-anchor="end"
                  class="svg-label mono"
                  fill="var(--text-3)"
                >
                  {{ yl.text }}
                </text>
              }

              <!-- x-axis labels -->
              @for (xl of b.xLabels; track xl.text) {
                <text
                  [attr.x]="xl.x"
                  [attr.y]="b.vbH - 4"
                  text-anchor="middle"
                  class="svg-label mono"
                  fill="var(--text-3)"
                >
                  {{ xl.text }}
                </text>
              }
            </svg>
          }
        </section>

        <!-- 3. Velocity -->
        <section class="card card-pad chart-card">
          <div class="sec-head">
            <span class="sec-title">Velocity</span>
            <span class="spacer"></span>
            <span class="legend">
              <span class="lg-item">
                <span class="swatch" style="background: var(--surface-3);"></span>
                Committed
              </span>
              <span class="lg-item">
                <span class="swatch" style="background: var(--accent);"></span>
                Completed
              </span>
            </span>
          </div>

          <div class="velocity">
            @for (c of velocity(); track c.sprint) {
              <div class="vcol">
                <div class="vbars">
                  <span
                    class="vbar committed"
                    [style.height.%]="c.committedPct"
                    [attr.title]="c.committed + ' committed'"
                  ></span>
                  <span
                    class="vbar completed"
                    [style.height.%]="c.completedPct"
                    [attr.title]="c.completed + ' completed'"
                  ></span>
                </div>
                <div class="vlabel mono">{{ c.sprint }}</div>
              </div>
            } @empty {
              <div class="empty-state" style="flex: 1;">No velocity data.</div>
            }
          </div>
        </section>

        <!-- 4. Work distribution -->
        <section class="card card-pad chart-card">
          <div class="sec-head">
            <span class="sec-title">Work distribution</span>
            <span class="chart-sub">{{ distTotal() }} issues</span>
          </div>

          <div class="dist-bar">
            @for (seg of distribution(); track seg.status) {
              <span
                class="dist-seg"
                [style.width.%]="seg.widthPct"
                [style.background]="seg.color"
                [attr.title]="seg.label + ': ' + seg.count"
              ></span>
            }
          </div>

          <div class="dist-legend">
            @for (seg of distribution(); track seg.status) {
              <span class="dl-item">
                <span class="dl-dot" [style.background]="seg.color"></span>
                <span class="dl-label">{{ seg.label }}</span>
                <span class="dl-count mono">{{ seg.count }}</span>
              </span>
            }
          </div>
        </section>
      } @else {
        <div class="empty-state">Loading reports…</div>
      }
    </div>
  `,
  styles: [
    `
      .head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        margin-bottom: 18px;
      }
      .spacer {
        flex: 1;
      }

      /* --- stat cards --- */
      .stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin-bottom: 14px;
      }
      .stat {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .stat-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-3);
      }
      .stat-value {
        display: flex;
        align-items: baseline;
        gap: 6px;
      }
      .stat-num {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text);
        line-height: 1;
      }
      .stat-unit {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-3);
      }
      .stat-delta {
        align-self: flex-start;
        padding: 3px 8px;
        border-radius: 7px;
        font-size: 11.5px;
        font-weight: 600;
        background: var(--success-soft);
        color: var(--success);
      }
      .stat-delta.bad {
        background: var(--danger-soft);
        color: var(--danger);
      }

      /* --- shared chart card --- */
      .chart-card {
        margin-bottom: 14px;
      }
      .chart-sub {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-3);
      }

      /* --- burndown --- */
      .burndown {
        display: block;
        width: 100%;
        height: auto;
        overflow: visible;
      }
      .svg-label {
        font-size: 10px;
        font-weight: 500;
      }
      .svg-label.mono {
        font-family: var(--font-mono);
      }

      /* --- velocity --- */
      .legend {
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .lg-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11.5px;
        font-weight: 500;
        color: var(--text-2);
      }
      .swatch {
        width: 10px;
        height: 10px;
        border-radius: 3px;
        display: inline-block;
      }
      .velocity {
        display: flex;
        align-items: flex-end;
        gap: 22px;
        height: 140px;
        padding: 0 4px;
      }
      .vcol {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        height: 100%;
        justify-content: flex-end;
      }
      .vbars {
        display: flex;
        align-items: flex-end;
        justify-content: center;
        gap: 5px;
        width: 100%;
        flex: 1;
      }
      .vbar {
        width: 26px;
        max-width: 42%;
        border-radius: 4px 4px 0 0;
        min-height: 2px;
        transition: height 0.3s ease;
      }
      .vbar.committed {
        background: var(--surface-3);
      }
      .vbar.completed {
        background: var(--accent);
      }
      .vlabel {
        font-size: 11px;
        font-weight: 500;
        color: var(--text-3);
        white-space: nowrap;
      }

      /* --- work distribution --- */
      .dist-bar {
        display: flex;
        width: 100%;
        height: 18px;
        border-radius: 9px;
        overflow: hidden;
        background: var(--surface-2);
        margin: 6px 0 14px;
      }
      .dist-seg {
        height: 100%;
        display: block;
        min-width: 1px;
      }
      .dist-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
      }
      .dl-item {
        display: flex;
        align-items: center;
        gap: 7px;
      }
      .dl-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .dl-label {
        font-size: 12.5px;
        font-weight: 500;
        color: var(--text-2);
      }
      .dl-count {
        font-size: 12px;
        font-weight: 600;
        color: var(--text-3);
      }
    `,
  ],
})
export class ReportsComponent {
  private views = inject(ViewsService);
  private ws = inject(WorkspaceStore);
  private monday = inject(MondayStore);

  private readonly reports = signal<Reports | undefined>(undefined);

  readonly data = this.reports.asReadonly();
  readonly spaceName = computed(() => this.ws.spaceInfo()?.name ?? 'Features');

  /** Precomputed burndown SVG geometry (undefined until data arrives). */
  readonly burndown = computed<BurndownGeom | undefined>(() => {
    const r = this.reports();
    if (!r) return undefined;
    const b = r.burndown;

    const vbW = 640;
    const vbH = 220;
    const padL = 34; // room for y-axis labels
    const padR = 12;
    const padT = 14;
    const padB = 26; // room for x-axis labels
    const innerW = vbW - padL - padR;
    const chartH = vbH - padT - padB;
    const baseY = padT + chartH;
    const max = b.max > 0 ? b.max : 1;

    // Map an array of remaining-work values to "x,y" polyline points.
    const toPts = (vals: number[]): string => {
      const n = vals.length;
      if (n === 0) return '';
      return vals
        .map((v, i) => {
          const x = padL + (n === 1 ? 0 : (i / (n - 1)) * innerW);
          const y = baseY - (Math.max(0, v) / max) * chartH;
          return `${round(x)},${round(y)}`;
        })
        .join(' ');
    };

    // Actual line points as {x,y} objects (reused for the polyline + area fill).
    // Plotted on the SAME day-scale as the ideal line (divide by total day steps,
    // not by the actual length) so "actual" stops at Today instead of being
    // stretched across the full chart width.
    const daySteps = Math.max(1, b.ideal.length - 1);
    const actualXY = b.actual.map((v, i) => ({
      x: round(padL + (i / daySteps) * innerW),
      y: round(baseY - (Math.max(0, v) / max) * chartH),
    }));

    const idealPts = toPts(b.ideal);
    const actualPts = actualXY.map((p) => `${p.x},${p.y}`).join(' ');
    const actualDots = actualXY.map((p, i) => ({
      x: p.x,
      y: p.y,
      label: `Day ${i}: ${b.actual[i]} pts left`,
    }));

    // Closed area under the actual line: baseline → line → baseline → close.
    let areaPath = '';
    if (actualXY.length > 0) {
      const firstX = actualXY[0].x;
      const lastX = actualXY[actualXY.length - 1].x;
      const line = actualXY.map((p) => `L ${p.x} ${p.y}`).join(' ');
      areaPath = `M ${firstX} ${round(baseY)} ${line} L ${lastX} ${round(baseY)} Z`;
    }

    // Today marker: actual is shorter than ideal; align it to the ideal axis.
    const idealLen = b.ideal.length;
    const actualLen = b.actual.length;
    const todayFrac =
      idealLen > 1 && actualLen > 0 ? (actualLen - 1) / (idealLen - 1) : 0;
    const todayX = padL + todayFrac * innerW;

    // Y-axis: max (top), mid, 0 (bottom).
    const yLabels = [
      { text: String(b.max), y: baseY - chartH },
      { text: String(Math.round(b.max / 2)), y: baseY - chartH / 2 },
      { text: '0', y: baseY },
    ];

    // X-axis: spread the provided day labels across the width.
    const days = b.days ?? [];
    const xLabels = days.map((text, i) => ({
      text,
      x: padL + (days.length <= 1 ? 0 : (i / (days.length - 1)) * innerW),
    }));

    return {
      vbW,
      vbH,
      innerW,
      chartH,
      padL,
      padT,
      idealPts,
      actualPts,
      areaPath,
      baseY,
      todayX: round(todayX),
      yLabels: yLabels.map((y) => ({ text: y.text, y: round(y.y) })),
      xLabels: xLabels.map((x) => ({ text: x.text, x: round(x.x) })),
      actualDots,
    };
  });

  /** Velocity columns with committed/completed heights as % of the shared max. */
  readonly velocity = computed<VelocityCol[]>(() => {
    const r = this.reports();
    if (!r) return [];
    const bars = r.velocity;
    const max = Math.max(
      1,
      ...bars.map((v) => Math.max(v.committed, v.completed)),
    );
    return bars.map((v) => ({
      sprint: v.sprint,
      committed: v.committed,
      completed: v.completed,
      committedPct: (v.committed / max) * 100,
      completedPct: (v.completed / max) * 100,
    }));
  });

  /** Total across all distribution slices (guarded against divide-by-zero). */
  readonly distTotal = computed<number>(() => {
    const r = this.reports();
    if (!r) return 0;
    return r.distribution.reduce((sum, s) => sum + s.count, 0);
  });

  /** Distribution segments with widths as a % of the total, colored by status. */
  readonly distribution = computed<DistSeg[]>(() => {
    const r = this.reports();
    if (!r) return [];
    const total = this.distTotal();
    return r.distribution.map((s) => ({
      status: s.status,
      label: s.label,
      count: s.count,
      color: STATUS_META[s.status].color,
      widthPct: total > 0 ? (s.count / total) * 100 : 0,
    }));
  });

  constructor() {
    // React to space + active-sprint changes.
    effect(() => {
      const space = this.ws.space();
      const sprint = this.ws.activeSprint()?.id;
      this.monday.syncTick();
      this.load(space, sprint);
    });
  }

  private load(space: Space, sprint?: string): void {
    this.views.reports(space, sprint).subscribe((r) => this.reports.set(r));
  }
}

/** Round SVG coordinates to keep the markup tidy (2 dp is plenty for charts). */
function round(n: number): number {
  return Math.round(n * 100) / 100;
}
