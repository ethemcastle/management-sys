import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AiPanelComponent } from './layout/ai-panel';
import { NewIssueModalComponent } from './layout/new-issue-modal';
import { SidebarComponent } from './layout/sidebar';
import { ToastHostComponent } from './layout/toast-host';
import { TopBarComponent } from './layout/top-bar';
import { WorkspaceStore } from './core/stores/workspace.store';

@Component({
  selector: 'app-root',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, SidebarComponent, TopBarComponent, AiPanelComponent, NewIssueModalComponent, ToastHostComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  readonly ws = inject(WorkspaceStore);

  ngOnInit(): void {
    this.ws.load();
  }
}
