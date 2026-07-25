import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { CatalogService } from '../../core/api/catalog.service';
import { IssuesService } from '../../core/api/issues.service';
import { YbugService } from '../../core/api/ybug.service';
import { CatalogItem } from '../../core/models';
import { MondayStore } from '../../core/stores/monday.store';
import { ToastStore } from '../../core/stores/toast.store';
import { WorkspaceStore } from '../../core/stores/workspace.store';
import { YbugStore } from '../../core/stores/ybug.store';
import { ZoomStore } from '../../core/stores/zoom.store';

type Kind = CatalogItem['kind'];

/** Settings / manage the option lists that populate ticket "Information" fields. */
@Component({
  selector: 'app-settings',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="view" style="max-width: 960px;">
      <header class="shead">
        <div class="eyebrow">Workspace</div>
        <h1 class="h1">Settings</h1>
        <p class="sub">Create and manage the values used across tickets. Changes apply everywhere.</p>
      </header>

      <!-- Integrations / monday.com -->
      <section class="card card-pad integ">
        <div class="lc-head">
          <span class="mdots"><svg width="16" height="16" viewBox="0 0 24 24">
            <circle cx="6" cy="12" r="2.6" fill="#ff3d57" /><circle cx="12" cy="12" r="2.6" fill="#ffcb00" />
            <circle cx="18" cy="12" r="2.6" fill="#00c875" /></svg></span>
          <span class="lc-title">monday.com</span>
          @if (monday.connected()) {
            <span class="badge on">Connected · {{ monday.accountName() }}</span>
          } @else {
            <span class="badge">Not connected</span>
          }
        </div>
        <p class="lc-hint">Two-way sync: tickets you create/edit here update monday, and Sync pulls monday's changes back.</p>
        <div class="integ-actions">
          @if (monday.connected()) {
            <button class="btn" [disabled]="monday.syncing()" (click)="monday.sync()">
              {{ monday.syncing() ? 'Syncing…' : 'Sync now' }}
            </button>
            <button class="btn" (click)="disconnectMonday()">Disconnect</button>
          } @else {
            <button class="btn btn-accent" (click)="monday.connect()">Connect monday.com</button>
          }
          <span class="sp"></span>
          <button class="btn danger" (click)="clearTickets()">Clear all tickets…</button>
        </div>
        <p class="lc-hint dnote">
          "Clear all tickets" removes every ticket but keeps your team, sprints, catalog, and the
          monday connection — use it to reset before importing your real monday workspace via Sync.
        </p>
      </section>

      <!-- Integrations / Zoom -->
      <section class="card card-pad integ">
        <div class="lc-head">
          <span class="zico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2D8CFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="12" height="12" rx="2.5" /><path d="M15 10l6-3v10l-6-3z" /></svg></span>
          <span class="lc-title">Zoom</span>
          @if (zoom.connected()) {
            <span class="badge on">Connected · {{ zoom.accountName() }}</span>
          } @else {
            <span class="badge">Not connected</span>
          }
        </div>
        <p class="lc-hint">Pulls the <b>AI Companion meeting summary</b> into a meeting's recap on the Calendar — with each next step turnable into a ticket.</p>
        <div class="integ-actions">
          @if (zoom.connected()) {
            <button class="btn" (click)="disconnectZoom()">Disconnect</button>
          } @else {
            <button class="btn btn-accent" (click)="connectZoom()">Connect Zoom</button>
          }
        </div>
        <p class="lc-hint dnote">
          Uses your paid Zoom plan (AI Companion is included). Add Server-to-Server OAuth creds
          (<span class="mono">CADENCE_ZOOM_*</span>) in <span class="mono">backend/.env</span> for real recaps; otherwise a demo recap is shown.
        </p>
      </section>

      <!-- Integrations / Ybug -->
      <section class="card card-pad integ">
        <div class="lc-head">
          <span class="yico"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C4DFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3h8l3 5-7 13L5 8z" /><path d="M3.5 8h17" /><path d="M12 8l-2.5 13M12 8l2.5 13" /></svg></span>
          <span class="lc-title">Ybug</span>
          @if (ybug.connected()) {
            <span class="badge on">Connected · {{ ybug.projectName() }}</span>
          } @else {
            <span class="badge">Not connected</span>
          }
        </div>
        <p class="lc-hint">Visual feedback from Ybug lands as a <b>ticket on the Board</b> — with reporter, page, browser/OS, console log and screenshot. {{ ybug.ticketCount() }} created so far.</p>
        <div class="integ-actions">
          @if (ybug.connected()) {
            <button class="btn btn-accent" (click)="simulateYbug()">Simulate a feedback</button>
            <button class="btn" (click)="syncYbug()">Sync now</button>
            <button class="btn" (click)="disconnectYbug()">Disconnect</button>
          } @else {
            <button class="btn btn-accent" (click)="ybug.connect()">Connect Ybug</button>
          }
        </div>
        <p class="lc-hint dnote">
          Real time: point Ybug's <b>feedback.created</b> webhook at <span class="mono">{{ webhookUrl }}</span> (needs a public URL).
          On localhost, use <b>Sync</b> (polls the Ybug API) or <b>Simulate</b> to try it. Add
          <span class="mono">CADENCE_YBUG_*</span> in <span class="mono">backend/.env</span> for your real project.
        </p>
      </section>

      <div class="grid">
        @for (g of groups; track g.kind) {
          <section class="card card-pad list-card">
            <div class="lc-head">
              <span class="lc-title">{{ g.title }}</span>
              <span class="lc-count">{{ itemsOf(g.kind).length }}</span>
            </div>
            <p class="lc-hint">{{ g.hint }}</p>

            <div class="rows">
              @for (it of itemsOf(g.kind); track it.id) {
                <div class="row">
                  <input class="rin" [value]="it.name" (change)="rename(it, $event)" />
                  <button class="del" (click)="remove(it)" title="Delete">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
                  </button>
                </div>
              }
              @if (itemsOf(g.kind).length === 0) {
                <div class="empty">Nothing yet — add one below.</div>
              }
            </div>

            <div class="addrow">
              <input class="rin" [placeholder]="'New ' + g.singular + '…'" [value]="draft()[g.kind]"
                (input)="setDraft(g.kind, $event)" (keydown.enter)="add(g.kind)" />
              <button class="btn btn-accent" [disabled]="!draft()[g.kind].trim()" (click)="add(g.kind)">Add</button>
            </div>
          </section>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .shead { margin-bottom: 22px; }
      .eyebrow { font-size: 12px; font-weight: 600; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }
      .h1 { font-size: 24px; font-weight: 750; color: var(--text); letter-spacing: -0.01em; margin: 3px 0 0; }
      .sub { font-size: 13.5px; color: var(--text-2); margin: 6px 0 0; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
      .lc-head { display: flex; align-items: baseline; gap: 8px; }
      .lc-title { font-size: 15px; font-weight: 700; color: var(--text); }
      .lc-count { font-size: 12px; color: var(--text-3); font-variant-numeric: tabular-nums; }
      .lc-hint { font-size: 12px; color: var(--text-3); margin: 3px 0 12px; }
      .rows { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
      .row { display: flex; align-items: center; gap: 8px; }
      .rin {
        flex: 1; min-width: 0; border: 1px solid var(--border); background: var(--surface-2);
        color: var(--text); border-radius: 8px; padding: 8px 10px; font-size: 13px; font-family: inherit; outline: none;
      }
      .rin:focus { border-color: var(--accent-line); }
      .del {
        width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
        border: 1px solid var(--border); background: var(--surface); color: var(--text-3);
        border-radius: 8px; cursor: pointer; flex-shrink: 0;
      }
      .del:hover { color: var(--danger, #d00000); border-color: var(--danger, #d00000); }
      .empty { font-size: 12.5px; color: var(--text-3); padding: 8px 2px; }
      .addrow { display: flex; gap: 8px; border-top: 1px solid var(--border); padding-top: 12px; }
      .addrow .btn[disabled] { opacity: 0.5; cursor: not-allowed; }
      .integ { margin-bottom: 16px; }
      .integ .lc-head { align-items: center; }
      .mdots, .zico, .yico { display: inline-flex; }
      .mono { font-family: var(--font-mono); font-size: 12px; color: var(--text-2); }
      .badge {
        font-size: 11.5px; font-weight: 600; color: var(--text-3);
        background: var(--surface-2); border-radius: 20px; padding: 2px 10px; margin-left: auto;
      }
      .badge.on { color: var(--success); background: var(--success-soft); }
      .integ-actions { display: flex; align-items: center; gap: 9px; margin-top: 4px; }
      .integ-actions .sp { flex: 1; }
      .integ-actions .btn[disabled] { opacity: 0.6; cursor: default; }
      .btn.danger { color: var(--danger); border-color: var(--border); }
      .btn.danger:hover { border-color: var(--danger); background: var(--danger-soft); }
      .dnote { margin-top: 10px; }
    `,
  ],
})
export class SettingsComponent {
  private api = inject(CatalogService);
  private ws = inject(WorkspaceStore);
  private issues = inject(IssuesService);
  private toast = inject(ToastStore);
  private router = inject(Router);
  private ybugApi = inject(YbugService);
  readonly monday = inject(MondayStore);
  readonly zoom = inject(ZoomStore);
  readonly ybug = inject(YbugStore);
  readonly webhookUrl = `${location.origin}/api/ybug/webhook`;

  readonly groups: { kind: Kind; title: string; singular: string; hint: string }[] = [
    { kind: 'product', title: 'Products', singular: 'product', hint: 'High-level product areas a ticket belongs to.' },
    { kind: 'component', title: 'Components', singular: 'component', hint: 'Parts of the system a ticket touches.' },
    { kind: 'release', title: 'Releases', singular: 'release', hint: 'Target release versions (e.g. 8.20.1).' },
  ];

  readonly items = signal<CatalogItem[]>([]);
  readonly draft = signal<Record<Kind, string>>({ product: '', component: '', release: '' });

  constructor() {
    this.reload();
  }

  private reload() {
    this.api.list().subscribe((i) => this.items.set(i));
  }
  private reloadAll() {
    this.reload();
    this.ws.refreshCatalog();
    this.ws.refreshCategories();
  }

  itemsOf(kind: Kind): CatalogItem[] {
    return this.items().filter((i) => i.kind === kind);
  }
  setDraft(kind: Kind, e: Event) {
    const v = (e.target as HTMLInputElement).value;
    this.draft.update((d) => ({ ...d, [kind]: v }));
  }
  add(kind: Kind) {
    const name = (this.draft()[kind] || '').trim();
    if (!name) return;
    this.api.create(kind, name).subscribe(() => {
      this.draft.update((d) => ({ ...d, [kind]: '' }));
      this.reloadAll();
    });
  }
  rename(item: CatalogItem, e: Event) {
    const name = (e.target as HTMLInputElement).value.trim();
    if (name && name !== item.name) this.api.rename(item.id, name).subscribe(() => this.reloadAll());
  }
  remove(item: CatalogItem) {
    this.api.delete(item.id).subscribe(() => this.reloadAll());
  }

  disconnectMonday() {
    if (!confirm('Disconnect monday.com? Existing tickets stay; two-way syncing stops.')) return;
    this.monday.disconnect();
  }

  connectZoom() {
    this.zoom.connect();
  }
  disconnectZoom() {
    if (!confirm('Disconnect Zoom? Existing recaps stay; new recaps use the demo generator.')) return;
    this.zoom.disconnect();
  }

  disconnectYbug() {
    if (!confirm('Disconnect Ybug? Existing tickets stay; new feedback stops creating tickets.')) return;
    this.ybug.disconnect();
  }
  simulateYbug() {
    this.ybugApi.simulate().subscribe((issue) => {
      this.ybug.refresh();
      this.toast.show(`Feedback → ${issue.key} on the board`, {
        actionLabel: 'Open',
        action: () => this.router.navigate(['/issues', issue.key]),
      });
    });
  }
  syncYbug() {
    this.ybugApi.sync().subscribe((r) => {
      this.ybug.refresh();
      this.toast.show(r.created ? `Imported ${r.created} feedback → tickets` : 'No new Ybug feedback');
    });
  }

  clearTickets() {
    if (
      !confirm(
        'Delete ALL tickets? This keeps team members, sprints, and catalog lists, but removes every ticket. This cannot be undone.',
      )
    )
      return;
    this.issues.clearDemo().subscribe((r) => {
      this.ws.refreshCategories();
      this.monday.refresh();
      this.toast.show(`Removed ${r.deleted} tickets. Hit Sync to import your monday workspace.`);
    });
  }
}
