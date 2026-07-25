import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { BootstrapService } from '../api/bootstrap.service';
import { CatalogService } from '../api/catalog.service';
import { IssuesService } from '../api/issues.service';
import { Categories, CatalogItem, Member, Role, Space, SpaceInfo, Sprint } from '../models';

type Theme = 'light' | 'dark';
type Density = 'comfortable' | 'compact';

const LS = {
  theme: 'cadence.theme',
  role: 'cadence.role',
  space: 'cadence.space',
  accent: 'cadence.accent',
  radius: 'cadence.radius',
  density: 'cadence.density',
};

function read(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

/** Global workspace state: role, space, theme + the static bootstrap data. */
@Injectable({ providedIn: 'root' })
export class WorkspaceStore {
  private bootstrapApi = inject(BootstrapService);
  private issuesApi = inject(IssuesService);
  private catalogApi = inject(CatalogService);

  // preferences (persisted)
  readonly role = signal<Role>(read(LS.role, 'developer') as Role);
  readonly space = signal<Space>(read(LS.space, 'features') as Space);
  readonly theme = signal<Theme>(read(LS.theme, 'light') as Theme);
  readonly accent = signal<string>(read(LS.accent, '#1f5b73'));
  readonly radius = signal<number>(Number(read(LS.radius, '12')));
  readonly density = signal<Density>(read(LS.density, 'comfortable') as Density);

  // bootstrap data
  readonly loaded = signal(false);
  readonly currentUser = signal<Member | null>(null);
  readonly members = signal<Member[]>([]);
  readonly spaces = signal<SpaceInfo[]>([]);
  readonly sprints = signal<Sprint[]>([]);
  readonly labels = signal<Record<string, string>>({});
  readonly categories = signal<Categories>({ products: [], components: [] });
  readonly catalog = signal<CatalogItem[]>([]);

  readonly productOptions = computed(() =>
    this.catalog().filter((c) => c.kind === 'product').map((c) => c.name),
  );
  readonly componentOptions = computed(() =>
    this.catalog().filter((c) => c.kind === 'component').map((c) => c.name),
  );
  readonly releaseOptions = computed(() =>
    this.catalog().filter((c) => c.kind === 'release').map((c) => c.name),
  );

  readonly activeSprint = computed(() => this.sprints().find((s) => s.active) ?? null);
  readonly spaceInfo = computed(
    () => this.spaces().find((s) => s.id === this.space()) ?? null,
  );

  readonly accentOptions = ['#1f5b73', '#003f75', '#2a7d6e', '#c16124', '#d00000'];

  constructor() {
    // Apply theme/accent/radius to <html> and persist any preference change.
    effect(() => {
      const el = document.documentElement;
      el.setAttribute('data-theme', this.theme());
      el.style.setProperty('--accent', this.accent());
      el.style.setProperty('--radius', `${this.radius()}px`);
      el.setAttribute('data-density', this.density());
      this.persist();
    });
  }

  load(): void {
    if (this.loaded()) return;
    this.bootstrapApi.get().subscribe((b) => {
      this.currentUser.set(b.currentUser);
      this.members.set(b.members);
      this.spaces.set(b.spaces);
      this.sprints.set(b.sprints);
      this.labels.set(b.labels);
      this.loaded.set(true);
    });
    this.refreshCategories();
    this.refreshCatalog();
  }

  /** Re-fetch the managed catalog (Products/Components/Releases). */
  refreshCatalog(): void {
    this.catalogApi.list().subscribe((c) => this.catalog.set(c));
  }

  /** Re-fetch sprints (e.g. after starting a sprint) so the active chip updates. */
  refreshSprints(): void {
    this.bootstrapApi.get().subscribe((b) => this.sprints.set(b.sprints));
  }

  /** Re-fetch the Product/Component category sections (after editing ticket info). */
  refreshCategories(): void {
    this.issuesApi.categories().subscribe((c) => this.categories.set(c));
  }

  setRole(role: Role) {
    this.role.set(role);
  }
  setSpace(space: Space) {
    this.space.set(space);
  }
  setTheme(theme: Theme) {
    this.theme.set(theme);
  }
  toggleTheme() {
    this.theme.update((t) => (t === 'light' ? 'dark' : 'light'));
  }
  setAccent(color: string) {
    this.accent.set(color);
  }
  setRadius(px: number) {
    this.radius.set(px);
  }
  setDensity(d: Density) {
    this.density.set(d);
  }

  private persist() {
    try {
      localStorage.setItem(LS.theme, this.theme());
      localStorage.setItem(LS.role, this.role());
      localStorage.setItem(LS.space, this.space());
      localStorage.setItem(LS.accent, this.accent());
      localStorage.setItem(LS.radius, String(this.radius()));
      localStorage.setItem(LS.density, this.density());
    } catch {
      /* ignore */
    }
  }
}
