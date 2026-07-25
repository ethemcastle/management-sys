import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { RecapsService } from '../../core/api/recaps.service';
import { MeetingNote } from '../../core/models';
import { RecapsStore } from '../../core/stores/recaps.store';
import { ToastStore } from '../../core/stores/toast.store';

@Component({
  selector: 'app-recaps',
  standalone: true,
  imports: [],
  templateUrl: './recaps.html',
  styleUrl: './recaps.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RecapsComponent {
  readonly store = inject(RecapsStore);
  private api = inject(RecapsService);
  private toast = inject(ToastStore);
  private router = inject(Router);

  readonly creating = signal<string | null>(null);
  readonly createdAll = signal<Set<number>>(new Set());
  readonly bulking = signal<number | null>(null);

  sync() {
    this.store.sync();
  }

  toAllTickets(r: MeetingNote) {
    this.bulking.set(r.id);
    this.api.createAll(r.id).subscribe({
      next: (issues) => {
        this.bulking.set(null);
        this.createdAll.update((s) => new Set(s).add(r.id));
        const n = issues.length;
        this.toast.show(`Created ${n} ticket${n === 1 ? '' : 's'} from “${r.title}”`);
      },
      error: () => {
        this.bulking.set(null);
        this.toast.show('Could not create the tickets', { tone: 'error' });
      },
    });
  }

  tag(recapId: number, index: number): string {
    return `${recapId}:${index}`;
  }

  toTicket(recapId: number, index: number, title: string) {
    this.creating.set(this.tag(recapId, index));
    this.api.actionItem(recapId, index).subscribe({
      next: (issue) => {
        this.creating.set(null);
        this.toast.show(`Created ${issue.key} · ${title}`, {
          actionLabel: 'Open',
          action: () => this.router.navigate(['/issues', issue.key]),
        });
      },
      error: () => {
        this.creating.set(null);
        this.toast.show('Could not create the ticket', { tone: 'error' });
      },
    });
  }

  fmtDate(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .map((p) => p[0] || '')
      .slice(0, 2)
      .join('')
      .toUpperCase();
  }

  isGroup(owner?: string): boolean {
    return !owner || owner.trim().toLowerCase() === 'the group';
  }
}
