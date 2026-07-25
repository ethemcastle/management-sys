import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** AI loading indicator: a spinner + staggered blinking dots + a message. */
@Component({
  selector: 'app-thinking-dots',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="row">
      <span class="spinner"></span>
      <span class="msg">{{ message() }}</span>
      <span class="dots">
        <span></span><span></span><span></span>
      </span>
    </span>
  `,
  styles: [
    `
      .row {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        color: var(--text-2);
        font-size: 13px;
      }
      .spinner {
        width: 15px;
        height: 15px;
        border-radius: 50%;
        border: 2px solid var(--ai-line);
        border-top-color: var(--ai);
        animation: cadSpin 0.8s linear infinite;
        flex-shrink: 0;
      }
      .dots {
        display: inline-flex;
        gap: 3px;
      }
      .dots > span {
        width: 4px;
        height: 4px;
        border-radius: 50%;
        background: var(--ai);
        animation: cadBlink 1.2s infinite;
      }
      .dots > span:nth-child(2) {
        animation-delay: 0.2s;
      }
      .dots > span:nth-child(3) {
        animation-delay: 0.4s;
      }
    `,
  ],
})
export class ThinkingDotsComponent {
  message = input('Thinking');
}
