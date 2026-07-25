import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { WorkspaceStore } from '../core/stores/workspace.store';
import { AiStore } from '../core/stores/ai.store';
import { Role, Space } from '../core/models';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
})
export class SidebarComponent {
  readonly ws = inject(WorkspaceStore);
  readonly ai = inject(AiStore);

  // Collapse state for the Product/Component category sections.
  readonly open = signal<Record<string, boolean>>({ products: true, components: true });

  toggle(key: string) {
    this.open.update((o) => ({ ...o, [key]: !o[key] }));
  }

  setSpace(space: Space) {
    this.ws.setSpace(space);
  }
  setRole(role: Role) {
    this.ws.setRole(role);
  }
  openAi() {
    this.ai.openPanel({ view: 'Home', space: this.ws.space() });
  }
}
