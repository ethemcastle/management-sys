// Semantic color coding from 04_DESIGN_TOKENS.md. Values are fixed; label/member
// colors come from the API. Helpers return colors + labels for presentational use.
import { CiStatus, EmailCategory, IssueType, PrState, ReviewState, Status } from './models';

export const TYPE_META: Record<IssueType, { letter: string; color: string }> = {
  story: { letter: 'S', color: '#2a7d6e' },
  bug: { letter: 'B', color: '#d00000' },
  task: { letter: 'T', color: '#0069b3' },
  epic: { letter: 'E', color: '#003f75' },
};

export const PRIORITY_META: { label: string; color: string }[] = [
  { label: 'Low', color: '#8c8c8d' },
  { label: 'Medium', color: '#db7b3e' },
  { label: 'High', color: '#c16124' },
  { label: 'Urgent', color: '#d00000' },
];

// Bar1 always the priority color; bar2 colored if priority>=1 else --border-2;
// bar3 colored if priority>=2. Heights 6/9/12px.
export function priorityBars(priority: number): string[] {
  const c = PRIORITY_META[priority]?.color ?? PRIORITY_META[0].color;
  const off = 'var(--border-2)';
  return [c, priority >= 1 ? c : off, priority >= 2 ? c : off];
}

export function priorityLabel(priority: number): string {
  return PRIORITY_META[priority]?.label ?? 'Low';
}

export const STATUS_META: Record<Status, { label: string; color: string }> = {
  backlog: { label: 'Backlog', color: '#8c8c8d' },
  todo: { label: 'To Do', color: '#8c8c8d' },
  inprogress: { label: 'In Progress', color: '#0069b3' },
  review: { label: 'In Review', color: '#db7b3e' },
  done: { label: 'Done', color: '#2a7d6e' },
};

export const PR_STATE_META: Record<PrState, { label: string; color: string }> = {
  open: { label: 'Open', color: '#0069b3' },
  draft: { label: 'Draft', color: '#8c8c8d' },
  merged: { label: 'Merged', color: '#003f75' },
};

export const CI_META: Record<CiStatus, { label: string; color: string }> = {
  passing: { label: 'Passing', color: '#2a7d6e' },
  failing: { label: 'Failing', color: '#d00000' },
  pending: { label: 'Pending', color: '#db7b3e' },
};

export const REVIEW_META: Record<ReviewState, { label: string; color: string }> = {
  approved: { label: 'Approved', color: '#2a7d6e' },
  pending: { label: 'Pending', color: '#db7b3e' },
  changes: { label: 'Changes requested', color: '#d00000' },
};

// Email categories (must match backend CATEGORY_META).
export const EMAIL_CATEGORY_META: Record<EmailCategory, { label: string; color: string }> = {
  customer: { label: 'Customer', color: '#0069b3' },
  internal: { label: 'Internal', color: '#1f5b73' },
  notification: { label: 'Notifications', color: '#8c8c8d' },
  newsletter: { label: 'Newsletters', color: '#a5a5a6' },
  alert: { label: 'Alerts', color: '#d00000' },
  meeting: { label: 'Meetings', color: '#003f75' },
};

export const IGNORE_FIELD_LABEL: Record<string, string> = {
  sender: 'From address',
  domain: 'Domain',
  category: 'Category',
  keyword: 'Keyword',
};

// Soft fill used by pills/chips: color at a low alpha via oklab mixing.
export function softFill(color: string, pct = 12): string {
  return `color-mix(in oklab, ${color} ${pct}%, transparent)`;
}
