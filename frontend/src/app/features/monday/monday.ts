import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { MondayService } from '../../core/api/monday.service';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { MondayColumn, MondayData, MondayItem } from '../../core/models';

interface ColumnView {
  title: string;
  items: MondayItem[];
}
interface BoardView {
  id: number;
  name: string;
  description: string;
  kind: string;
  url: string | null;
  itemCount: number;
  columns: ColumnView[];
}

@Component({
  selector: 'app-monday',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  templateUrl: './monday.html',
  styleUrl: './monday.scss',
})
export class MondayComponent {
  private api = inject(MondayService);
  private ws = inject(WorkspaceStore);

  readonly data = signal<MondayData | null>(null);
  readonly connecting = signal(false);
  readonly refreshing = signal(false);

  readonly account = computed(() => this.data()?.account ?? null);

  /** Each board rendered as a kanban whose columns are its monday groups. */
  readonly boards = computed<BoardView[]>(() => {
    const d = this.data();
    if (!d || !d.account.connected) return [];
    return d.boards.map((b) => {
      const columns: ColumnView[] = [];
      const byTitle = new Map<string, MondayItem[]>();
      for (const it of b.items) {
        const t = it.group || 'Items';
        let bucket = byTitle.get(t);
        if (!bucket) {
          bucket = [];
          byTitle.set(t, bucket);
          columns.push({ title: t, items: bucket });
        }
        bucket.push(it);
      }
      return {
        id: b.id,
        name: b.name,
        description: b.description,
        kind: b.kind,
        url: b.url,
        itemCount: b.itemCount,
        columns,
      };
    });
  });

  readonly totalItems = computed(
    () => this.data()?.boards.reduce((n, b) => n + b.itemCount, 0) ?? 0,
  );
  readonly importedCount = computed(
    () =>
      this.data()?.boards.reduce(
        (n, b) => n + b.items.filter((i) => i.imported).length,
        0,
      ) ?? 0,
  );

  constructor() {
    this.load();
  }

  private load() {
    this.api.get().subscribe((d) => this.data.set(d));
  }

  /** Refresh the page data and the sidebar category sections together, so the
   *  monday boards show up as categories the moment their tickets are imported. */
  private reloadAll() {
    this.load();
    this.ws.refreshCategories();
  }

  connect() {
    this.connecting.set(true);
    this.api.connect().subscribe({
      next: () => {
        this.connecting.set(false);
        this.reloadAll();
      },
      error: () => this.connecting.set(false),
    });
  }

  refresh() {
    if (this.refreshing()) return;
    this.refreshing.set(true);
    this.api.sync().subscribe({
      next: () => {
        this.refreshing.set(false);
        this.reloadAll();
      },
      error: () => this.refreshing.set(false),
    });
  }

  disconnect() {
    this.api.disconnect().subscribe(() => this.reloadAll());
  }

  /** Card fields beyond status/owner (which already have their own UI). */
  extraFields(it: MondayItem): MondayColumn[] {
    return (it.columns || []).filter((c) => !/status|owner|person|people/i.test(c.title));
  }
}
