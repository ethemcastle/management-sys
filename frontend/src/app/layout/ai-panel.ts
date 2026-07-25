import { ChangeDetectionStrategy, Component, ElementRef, inject, viewChild } from '@angular/core';
import { AiStore } from '../core/stores/ai.store';
import { ThinkingDotsComponent } from '../shared/thinking-dots';

@Component({
  selector: 'app-ai-panel',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ThinkingDotsComponent],
  template: `
    @if (ai.panelOpen()) {
      <div class="scrim" (click)="ai.closePanel()"></div>
      <aside class="panel" role="dialog" aria-label="risr/crm AI">
        <div class="phead">
          <span class="tile">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="#fff">
              <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" /></svg>
          </span>
          <div class="ptitle">
            <span class="pn">risr/crm AI</span>
            <span class="ps">Context-aware assistant</span>
          </div>
          <button class="x" (click)="ai.closePanel()" aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="1.9" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        <div class="pbody">
          <div class="ctx">
            Looking at <b>{{ ai.panelContext().view }}</b> · {{ ai.panelContext().space }}
          </div>

          @switch (ai.panelPhase()) {
            @case ('busy') {
              <div class="busy"><app-thinking-dots message="Analyzing your workspace" /></div>
            }
            @case ('done') {
              <div class="done cad-fade">
                <div class="dtitle">Here's what I found</div>
                <ul class="bullets">
                  @for (b of ai.panelBullets(); track $index) { <li>{{ b }}</li> }
                </ul>
                <div class="drow">
                  <button class="mini" (click)="copy()">Copy</button>
                  <button class="mini" (click)="ai.resetPanel()">New question</button>
                </div>
              </div>
            }
            @default {
              <div class="try">
                <div class="tlabel">Try asking</div>
                @for (s of suggestions; track s) {
                  <button class="chip" (click)="ask(s)">{{ s }}</button>
                }
              </div>
              <div class="empty">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--ai-line)"
                  stroke-width="1.6"><path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" /></svg>
                <p>Ask anything about this workspace — I read the issues, PRs, and CI live.</p>
              </div>
            }
          }
        </div>

        <div class="pfoot">
          <input #q type="text" placeholder="Ask risr/crm AI…" (keydown.enter)="ask(q.value); q.value = ''" />
          <button class="send" (click)="ask(q.value); q.value = ''" aria-label="Send">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6" /></svg>
          </button>
        </div>
      </aside>
    }
  `,
  styles: [
    `
      .scrim {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.32);
        z-index: 40;
      }
      .panel {
        position: fixed;
        top: 0;
        right: 0;
        height: 100vh;
        width: 414px;
        max-width: 92vw;
        background: var(--surface);
        border-left: 1px solid var(--border);
        box-shadow: var(--shadow-pop);
        z-index: 41;
        display: flex;
        flex-direction: column;
        animation: cadSlideR 0.28s cubic-bezier(0.22, 1, 0.36, 1);
      }
      .phead {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 15px 16px;
        border-bottom: 1px solid var(--border);
      }
      .tile {
        width: 31px;
        height: 31px;
        border-radius: 9px;
        background: linear-gradient(140deg, var(--ai), var(--accent));
        display: grid;
        place-items: center;
        flex-shrink: 0;
      }
      .ptitle {
        display: flex;
        flex-direction: column;
        line-height: 1.2;
        flex: 1;
      }
      .pn {
        font-size: 14.5px;
        font-weight: 700;
        color: var(--text);
      }
      .ps {
        font-size: 11px;
        color: var(--text-3);
      }
      .x {
        border: none;
        background: transparent;
        color: var(--text-3);
        cursor: pointer;
        padding: 4px;
        border-radius: 6px;
      }
      .x:hover {
        background: var(--surface-2);
        color: var(--text);
      }
      .pbody {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 14px;
      }
      .ctx {
        font-size: 12px;
        color: var(--text-2);
        background: var(--surface-2);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 8px 11px;
      }
      .ctx b {
        color: var(--text);
      }
      .try {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .tlabel {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-3);
      }
      .chip {
        text-align: left;
        padding: 10px 12px;
        border-radius: 9px;
        border: 1px solid var(--ai-line);
        background: var(--ai-soft);
        color: var(--text);
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        font-family: inherit;
      }
      .chip:hover {
        border-color: var(--ai);
      }
      .empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        text-align: center;
        color: var(--text-3);
        padding: 30px 20px;
      }
      .empty p {
        font-size: 12.5px;
        margin: 0;
        max-width: 240px;
      }
      .busy {
        padding: 24px 4px;
      }
      .done .dtitle {
        font-size: 13px;
        font-weight: 700;
        color: var(--text);
        margin-bottom: 10px;
      }
      .bullets {
        margin: 0;
        padding-left: 18px;
        display: flex;
        flex-direction: column;
        gap: 9px;
      }
      .bullets li {
        font-size: 13px;
        line-height: 1.5;
        color: var(--text-2);
      }
      .drow {
        display: flex;
        gap: 8px;
        margin-top: 14px;
      }
      .mini {
        padding: 6px 12px;
        border-radius: 7px;
        border: 1px solid var(--border);
        background: var(--surface-2);
        color: var(--text-2);
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
      }
      .mini:hover {
        color: var(--text);
        border-color: var(--border-2);
      }
      .pfoot {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px 14px;
        border-top: 1px solid var(--border);
      }
      .pfoot input {
        flex: 1;
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 10px 12px;
        background: var(--surface-2);
        color: var(--text);
        font-size: 13px;
        outline: none;
        font-family: inherit;
      }
      .pfoot input:focus {
        border-color: var(--ai-line);
      }
      .send {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        border: none;
        background: var(--ai);
        color: #fff;
        display: grid;
        place-items: center;
        cursor: pointer;
        flex-shrink: 0;
      }
      .send:hover {
        filter: brightness(1.06);
      }
    `,
  ],
})
export class AiPanelComponent {
  readonly ai = inject(AiStore);
  private input = viewChild<ElementRef<HTMLInputElement>>('q');

  readonly suggestions = [
    'Summarize this sprint',
    "What's at risk?",
    'Draft release notes',
    'Find stale PRs',
  ];

  ask(question: string) {
    if (!question.trim()) return;
    this.ai.ask(question);
  }

  copy() {
    const text = this.ai.panelBullets().map((b) => `• ${b}`).join('\n');
    navigator.clipboard?.writeText(text).catch(() => {});
  }
}
