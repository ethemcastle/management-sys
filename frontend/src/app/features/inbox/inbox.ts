import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';

import { EmailsService } from '../../core/api/emails.service';
import {
  Email,
  EmailCategory,
  EmailDetail,
  IgnoreField,
  IgnoreRule,
  Inbox,
  InboxRecap,
} from '../../core/models';
import { EMAIL_CATEGORY_META, IGNORE_FIELD_LABEL, softFill } from '../../core/theme';
import { ThinkingDotsComponent } from '../../shared/thinking-dots';

type RecapPhase = 'idle' | 'busy' | 'done';

@Component({
  selector: 'app-inbox',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ThinkingDotsComponent],
  templateUrl: './inbox.html',
  styleUrl: './inbox.scss',
})
export class InboxComponent {
  private api = inject(EmailsService);

  readonly catMeta = EMAIL_CATEGORY_META;
  readonly fieldLabel = IGNORE_FIELD_LABEL;
  readonly softFill = softFill;

  readonly inbox = signal<Inbox | null>(null);
  readonly rules = signal<IgnoreRule[]>([]);
  readonly activeCategory = signal<EmailCategory | null>(null);
  readonly showIgnored = signal(false);
  readonly showRules = signal(false);
  readonly selectedId = signal<number | null>(null);
  readonly selectedEmail = signal<EmailDetail | null>(null);

  readonly recap = signal<InboxRecap | null>(null);
  readonly recapPhase = signal<RecapPhase>('idle');

  // add-rule form
  readonly addField = signal<IgnoreField>('category');
  readonly addValue = signal('');
  readonly fields: IgnoreField[] = ['category', 'sender', 'domain', 'keyword'];
  readonly categories: EmailCategory[] = [
    'customer',
    'internal',
    'notification',
    'newsletter',
    'alert',
    'meeting',
  ];

  readonly total = computed(() =>
    (this.inbox()?.categories ?? []).reduce((n, b) => n + b.count, 0),
  );

  constructor() {
    effect(() => {
      const cat = this.activeCategory();
      const incl = this.showIgnored();
      this.loadInbox(cat, incl);
    });
    this.loadRules();
  }

  private loadInbox(cat: EmailCategory | null, includeIgnored: boolean) {
    this.api.inbox(cat, includeIgnored).subscribe((i) => this.inbox.set(i));
  }
  private loadRules() {
    this.api.listRules().subscribe((r) => this.rules.set(r));
  }
  private reload() {
    this.loadInbox(this.activeCategory(), this.showIgnored());
    this.loadRules();
  }

  setCategory(cat: EmailCategory | null) {
    this.activeCategory.set(cat);
  }
  toggleIgnored() {
    this.showIgnored.update((v) => !v);
  }
  toggleRules() {
    this.showRules.update((v) => !v);
  }

  select(email: Email) {
    if (this.selectedId() === email.id) {
      this.selectedId.set(null);
      this.selectedEmail.set(null);
      return;
    }
    this.selectedId.set(email.id);
    this.selectedEmail.set(null);
    this.api.get(email.id).subscribe((d) => this.selectedEmail.set(d));
    if (email.unread) {
      this.api.patch(email.id, { unread: false }).subscribe(() => {
        this.inbox.update((inb) =>
          inb
            ? { ...inb, emails: inb.emails.map((e) => (e.id === email.id ? { ...e, unread: false } : e)) }
            : inb,
        );
      });
    }
  }

  doRecap() {
    this.recapPhase.set('busy');
    this.recap.set(null);
    this.api.recap().subscribe((r) => {
      this.recap.set(r);
      this.recapPhase.set('done');
    });
  }
  copyRecap() {
    const r = this.recap();
    if (!r) return;
    navigator.clipboard?.writeText(r.bullets.map((b) => `• ${b}`).join('\n')).catch(() => {});
  }

  ignoreSender(e: Email, ev: Event) {
    ev.stopPropagation();
    this.api.createRule('sender', e.senderEmail).subscribe(() => this.reload());
  }
  ignoreCategory(e: Email, ev: Event) {
    ev.stopPropagation();
    this.api.createRule('category', e.category).subscribe(() => this.reload());
  }

  addRule() {
    const value = this.addValue().trim();
    if (!value) return;
    this.api.createRule(this.addField(), value).subscribe(() => {
      this.addValue.set('');
      this.reload();
    });
  }
  removeRule(id: number) {
    this.api.deleteRule(id).subscribe(() => this.reload());
  }

  onField(e: Event) {
    this.addField.set((e.target as HTMLSelectElement).value as IgnoreField);
  }
  onValue(e: Event) {
    this.addValue.set((e.target as HTMLInputElement).value);
  }

  senderInitials(name: string): string {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
  }

  rel(iso: string): string {
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m`;
    if (s < 86400) return `${Math.round(s / 3600)}h`;
    return `${Math.round(s / 86400)}d`;
  }
}
