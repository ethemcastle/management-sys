import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';

import { Router, RouterLink } from '@angular/router';

import { CalendarService } from '../../core/api/calendar.service';
import { CalendarData, CalendarEvent } from '../../core/models';
import { ToastStore } from '../../core/stores/toast.store';
import { ThinkingDotsComponent } from '../../shared/thinking-dots';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

interface Positioned {
  event: CalendarEvent;
  top: number;
  height: number;
  leftPct: number;
  widthPct: number;
  color: string;
  short: boolean;
}

interface Day {
  label: string;
  dayNum: number;
  iso: string;
  isToday: boolean;
  positioned: Positioned[];
}

@Component({
  selector: 'app-calendar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ThinkingDotsComponent, RouterLink],
  templateUrl: './calendar.html',
  styleUrl: './calendar.scss',
})
export class CalendarComponent {
  private api = inject(CalendarService);
  private toast = inject(ToastStore);
  private router = inject(Router);

  // Time-grid geometry (Google-Calendar-style week view).
  readonly DAY_START = 0; // midnight — full day so any event is visible
  readonly DAY_END = 24;
  readonly HOUR_H = 44; // px per hour
  readonly gridHeight = (this.DAY_END - this.DAY_START) * this.HOUR_H;
  readonly hoursLabels = Array.from(
    { length: this.DAY_END - this.DAY_START + 1 },
    (_, i) => this.DAY_START + i,
  );
  private readonly PALETTE = [
    'var(--info)',
    'var(--ai)',
    'var(--success)',
    'var(--warning)',
    'var(--accent)',
    '#0E7C86',
  ];

  readonly data = signal<CalendarData | null>(null);
  readonly connecting = signal(false);
  readonly selectedId = signal<number | null>(null);
  readonly recapBusy = signal(false);
  // Per-next-step ticket state (keyed by action-item index within the open recap).
  readonly creating = signal<number | null>(null);
  readonly ticketFor = signal<Record<number, string>>({});

  readonly account = computed(() => this.data()?.account ?? null);
  readonly selected = computed(
    () => this.data()?.events.find((e) => e.id === this.selectedId()) ?? null,
  );
  readonly eventCount = computed(() => this.data()?.events.length ?? 0);

  readonly days = computed<Day[]>(() => {
    const d = this.data();
    if (!d || !d.account.connected) return [];
    const start = new Date(d.weekStart);
    const today = new Date();
    const out: Day[] = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(start);
      date.setDate(start.getDate() + i);
      const dayEvents = d.events.filter((e) => this.sameDay(new Date(e.start), date));
      out.push({
        label: WEEKDAYS[date.getDay()],
        dayNum: date.getDate(),
        iso: date.toISOString().slice(0, 10),
        isToday: this.sameDay(date, today),
        positioned: this.layoutDay(dayEvents),
      });
    }
    return out;
  });

  readonly weekLabel = computed(() => {
    const d = this.data();
    if (!d) return '';
    const s = new Date(d.weekStart);
    const e = new Date(d.weekEnd);
    e.setDate(e.getDate() - 1);
    const fmt = (x: Date) =>
      new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(x);
    return `${fmt(s)} – ${fmt(e)}, ${s.getFullYear()}`;
  });

  // Position of the "now" line within the grid (null if outside the window).
  readonly nowTop = computed(() => {
    const now = new Date();
    const min = now.getHours() * 60 + now.getMinutes() - this.DAY_START * 60;
    if (min < 0 || min > (this.DAY_END - this.DAY_START) * 60) return null;
    return (min / 60) * this.HOUR_H;
  });

  readonly tz = (() => {
    const o = -new Date().getTimezoneOffset() / 60;
    return 'GMT' + (o >= 0 ? '+' : '') + o;
  })();

  private scrollEl = viewChild<ElementRef<HTMLDivElement>>('gscroll');

  constructor() {
    this.load();
  }

  private load(week?: string) {
    this.api.get(week).subscribe((d) => {
      this.data.set(d);
      // On first paint of a full-day grid, scroll to ~7am so it isn't stuck at midnight.
      setTimeout(() => {
        const el = this.scrollEl()?.nativeElement;
        if (el && el.scrollTop === 0) el.scrollTop = 7 * this.HOUR_H;
      }, 60);
    });
  }

  /** Shift the shown week by ±7 days (from whatever week is currently loaded). */
  private shiftWeek(deltaDays: number) {
    const d = this.data();
    if (!d) return;
    const monday = new Date(d.weekStart);
    monday.setDate(monday.getDate() + deltaDays);
    this.load(monday.toISOString().slice(0, 10));
  }
  prevWeek() {
    this.shiftWeek(-7);
  }
  nextWeek() {
    this.shiftWeek(7);
  }
  goToday() {
    this.load();
  }

  connect() {
    this.connecting.set(true);
    this.api.connect().subscribe({
      next: () => {
        this.connecting.set(false);
        this.load();
      },
      error: () => this.connecting.set(false),
    });
  }

  disconnect() {
    this.api.disconnect().subscribe(() => {
      this.selectedId.set(null);
      this.load();
    });
  }

  select(e: CalendarEvent) {
    this.selectedId.set(e.id);
    this.ticketFor.set({}); // reset per-recap ticket state for the new event
    this.creating.set(null);
  }
  closePanel() {
    this.selectedId.set(null);
  }

  /** Turn a recap next-step into a risr/crm ticket. */
  createTicket(recapId: number, index: number) {
    if (this.creating() !== null || this.ticketFor()[index]) return;
    this.creating.set(index);
    this.api.actionItemToTicket(recapId, index).subscribe({
      next: (issue) => {
        this.creating.set(null);
        this.ticketFor.update((m) => ({ ...m, [index]: issue.key }));
        this.toast.show(`Created ${issue.key}`, {
          actionLabel: 'Open',
          action: () => this.router.navigate(['/issues', issue.key]),
        });
      },
      error: () => this.creating.set(null),
    });
  }

  generateRecap(e: CalendarEvent) {
    this.recapBusy.set(true);
    this.api.recapEvent(e.id).subscribe((res) => {
      this.data.update((d) =>
        d ? { ...d, events: d.events.map((ev) => (ev.id === res.event.id ? res.event : ev)) } : d,
      );
      this.recapBusy.set(false);
    });
  }

  /** Lay out a day's events into time-positioned blocks with overlap columns. */
  private layoutDay(events: CalendarEvent[]): Positioned[] {
    const items = events
      .map((e) => {
        const s = new Date(e.start);
        const en = new Date(e.end);
        return { e, startMin: s.getHours() * 60 + s.getMinutes(), endMin: en.getHours() * 60 + en.getMinutes() };
      })
      .sort((a, b) => a.startMin - b.startMin || a.endMin - b.endMin);

    const out: Positioned[] = [];
    let cluster: typeof items = [];
    let clusterEnd = -1;

    const flush = () => {
      if (!cluster.length) return;
      const lanes: number[] = [];
      const colOf = new Map<(typeof items)[number], number>();
      for (const it of cluster) {
        let placed = -1;
        for (let i = 0; i < lanes.length; i++) {
          if (lanes[i] <= it.startMin) {
            placed = i;
            break;
          }
        }
        if (placed === -1) {
          placed = lanes.length;
          lanes.push(0);
        }
        lanes[placed] = it.endMin;
        colOf.set(it, placed);
      }
      const cols = lanes.length;
      for (const it of cluster) {
        const topMin = it.startMin - this.DAY_START * 60;
        const durMin = Math.max(20, it.endMin - it.startMin);
        const col = colOf.get(it) ?? 0;
        const widthPct = 100 / cols;
        out.push({
          event: it.e,
          top: (topMin / 60) * this.HOUR_H,
          height: Math.max(20, (durMin / 60) * this.HOUR_H - 3),
          leftPct: col * widthPct,
          widthPct,
          color: this.colorFor(it.e),
          short: it.endMin - it.startMin <= 30,
        });
      }
      cluster = [];
      clusterEnd = -1;
    };

    for (const it of items) {
      if (cluster.length && it.startMin >= clusterEnd) flush();
      cluster.push(it);
      clusterEnd = Math.max(clusterEnd, it.endMin);
    }
    flush();
    return out;
  }

  private colorFor(e: CalendarEvent): string {
    return this.PALETTE[(e.id - 1) % this.PALETTE.length];
  }

  private sameDay(a: Date, b: Date): boolean {
    return (
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate()
    );
  }

  hourLabel(h: number): string {
    const ap = h < 12 ? 'AM' : 'PM';
    const hr = h % 12 === 0 ? 12 : h % 12;
    return `${hr} ${ap}`;
  }

  time(iso: string): string {
    return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(
      new Date(iso),
    );
  }
  range(e: CalendarEvent): string {
    return `${this.time(e.start)} – ${this.time(e.end)}`;
  }
}
