import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  output,
  signal,
} from '@angular/core';

/** Searchable dropdown that can create a new value inline when none matches.
 *  Emits `changed` with the chosen value (existing or newly typed), or null on clear. */
@Component({
  selector: 'app-combobox',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="cb">
      <button type="button" class="cb-trigger" (click)="toggle()">
        <span class="cb-val" [class.ph]="!value()">{{ value() || placeholder() }}</span>
        <svg class="cb-caret" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      @if (open()) {
        <div class="cb-scrim" (click)="close()"></div>
        <div class="cb-panel">
          <input class="cb-search" autofocus [value]="search()" (input)="onSearch($event)"
            (keydown.enter)="enter(); $event.preventDefault()" (keydown.escape)="close()"
            [placeholder]="'Search or create…'" />
          <div class="cb-opts">
            @for (o of filtered(); track o) {
              <button type="button" class="cb-opt" [class.sel]="o === value()" (click)="pick(o)">
                {{ o }}
                @if (o === value()) {
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4 4 10-10" /></svg>
                }
              </button>
            }
            @if (canCreate()) {
              <button type="button" class="cb-opt cb-create" (click)="create()">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14" /></svg>
                Create “{{ search().trim() }}”
              </button>
            }
            @if (!filtered().length && !canCreate()) {
              <div class="cb-empty">No matches</div>
            }
          </div>
          @if (value() && clearable()) {
            <button type="button" class="cb-clear" (click)="pick(null)">Clear</button>
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      .cb {
        position: relative;
        width: 100%;
      }
      .cb-trigger {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
        border: 1px solid var(--border);
        background: var(--surface-2);
        color: var(--text);
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
        font-family: inherit;
        cursor: pointer;
        text-align: left;
      }
      .cb-trigger:hover {
        border-color: var(--border-2);
      }
      .cb-val {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .cb-val.ph {
        color: var(--text-3);
      }
      .cb-caret {
        color: var(--text-3);
        flex-shrink: 0;
      }
      .cb-scrim {
        position: fixed;
        inset: 0;
        z-index: 40;
      }
      .cb-panel {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        min-width: 200px;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: var(--shadow-pop);
        padding: 6px;
        z-index: 41;
      }
      .cb-search {
        width: 100%;
        border: 1px solid var(--border);
        background: var(--surface-2);
        color: var(--text);
        border-radius: 7px;
        padding: 7px 9px;
        font-size: 13px;
        font-family: inherit;
        outline: none;
        margin-bottom: 5px;
      }
      .cb-search:focus {
        border-color: var(--accent-line);
      }
      .cb-opts {
        max-height: 220px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 1px;
      }
      .cb-opt {
        display: flex;
        align-items: center;
        gap: 7px;
        width: 100%;
        padding: 7px 8px;
        border: none;
        background: transparent;
        border-radius: 7px;
        cursor: pointer;
        font-family: inherit;
        font-size: 13px;
        color: var(--text);
        text-align: left;
      }
      .cb-opt svg {
        margin-left: auto;
        color: var(--accent);
      }
      .cb-opt:hover {
        background: var(--surface-2);
      }
      .cb-opt.sel {
        color: var(--accent);
        font-weight: 600;
      }
      .cb-create {
        color: var(--accent);
        font-weight: 600;
      }
      .cb-create svg {
        margin-left: 0;
      }
      .cb-empty {
        padding: 8px;
        font-size: 12.5px;
        color: var(--text-3);
      }
      .cb-clear {
        width: 100%;
        margin-top: 5px;
        padding: 6px;
        border: none;
        border-top: 1px solid var(--border);
        background: transparent;
        color: var(--text-3);
        font-size: 12px;
        font-family: inherit;
        cursor: pointer;
      }
      .cb-clear:hover {
        color: var(--text);
      }
    `,
  ],
})
export class ComboboxComponent {
  readonly options = input<string[]>([]);
  readonly value = input<string | null>(null);
  readonly placeholder = input('Select…');
  readonly allowCreate = input(true);
  readonly clearable = input(true);
  readonly changed = output<string | null>();

  readonly open = signal(false);
  readonly search = signal('');

  readonly filtered = computed(() => {
    const q = this.search().trim().toLowerCase();
    return this.options().filter((o) => !q || o.toLowerCase().includes(q));
  });
  readonly canCreate = computed(() => {
    const q = this.search().trim();
    return this.allowCreate() && !!q && !this.options().some((o) => o.toLowerCase() === q.toLowerCase());
  });

  toggle() {
    this.open.update((v) => !v);
    if (this.open()) this.search.set('');
  }
  close() {
    this.open.set(false);
  }
  onSearch(e: Event) {
    this.search.set((e.target as HTMLInputElement).value);
  }
  pick(o: string | null) {
    this.changed.emit(o);
    this.close();
  }
  create() {
    const v = this.search().trim();
    if (v) this.pick(v);
  }
  enter() {
    if (this.filtered().length) this.pick(this.filtered()[0]);
    else if (this.canCreate()) this.create();
  }
}
