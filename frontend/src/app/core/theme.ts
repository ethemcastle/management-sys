// Semantic color coding from 04_DESIGN_TOKENS.md. Values are fixed; label/member
// colors come from the API. Helpers return colors + labels for presentational use.
import { CiStatus, EmailCategory, IssueType, PrState, ReviewState, Status } from './models';

export const TYPE_META: Record<IssueType, { letter: string; color: string }> = {
  story: { letter: 'S', color: '#2E9E5B' },
  bug: { letter: 'B', color: '#D95340' },
  task: { letter: 'T', color: '#3B7DD8' },
  epic: { letter: 'E', color: '#8B5CF6' },
};

export const PRIORITY_META: { label: string; color: string }[] = [
  { label: 'Low', color: '#9A998F' },
  { label: 'Medium', color: '#C0A227' },
  { label: 'High', color: '#E8833A' },
  { label: 'Urgent', color: '#D95340' },
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
  backlog: { label: 'Backlog', color: '#9A998F' },
  todo: { label: 'To Do', color: '#9A998F' },
  inprogress: { label: 'In Progress', color: '#3B7DD8' },
  review: { label: 'In Review', color: '#C0A227' },
  done: { label: 'Done', color: '#2E9E5B' },
};

export const PR_STATE_META: Record<PrState, { label: string; color: string }> = {
  open: { label: 'Open', color: '#3B7DD8' },
  draft: { label: 'Draft', color: '#9A998F' },
  merged: { label: 'Merged', color: '#8B5CF6' },
};

export const CI_META: Record<CiStatus, { label: string; color: string }> = {
  passing: { label: 'Passing', color: '#2E9E5B' },
  failing: { label: 'Failing', color: '#D95340' },
  pending: { label: 'Pending', color: '#C0A227' },
};

export const REVIEW_META: Record<ReviewState, { label: string; color: string }> = {
  approved: { label: 'Approved', color: '#2E9E5B' },
  pending: { label: 'Pending', color: '#C0A227' },
  changes: { label: 'Changes requested', color: '#D95340' },
};

// Email categories (must match backend CATEGORY_META).
export const EMAIL_CATEGORY_META: Record<EmailCategory, { label: string; color: string }> = {
  customer: { label: 'Customer', color: '#3B7DD8' },
  internal: { label: 'Internal', color: '#5A50E1' },
  notification: { label: 'Notifications', color: '#9A998F' },
  newsletter: { label: 'Newsletters', color: '#95948B' },
  alert: { label: 'Alerts', color: '#D95340' },
  meeting: { label: 'Meetings', color: '#8B5CF6' },
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
