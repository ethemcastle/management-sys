// TypeScript interfaces mirroring the risr/crm API (camelCase JSON).

export type IssueType = 'story' | 'bug' | 'task' | 'epic';
export type Status = 'backlog' | 'todo' | 'inprogress' | 'review' | 'done';
export type Space = 'features' | 'support';
export type PrState = 'open' | 'draft' | 'merged';
export type CiStatus = 'passing' | 'failing' | 'pending';
export type ReviewState = 'approved' | 'pending' | 'changes';
export type Role = 'developer' | 'product_owner';

export interface Member {
  initials: string;
  name: string;
  color: string;
  role: Role;
  isCurrentUser?: boolean;
}

export interface MemberRef {
  initials: string;
  name: string;
  color: string;
}

export interface SpaceInfo {
  id: Space;
  name: string;
  sub: string;
  kind: string;
}

export interface Sprint {
  id: string;
  name: string;
  range: string;
  goal: string;
  daysLeft: number | null;
  daysTotal: number;
  capacity: number | null;
  active: boolean;
}

export interface Label {
  name: string;
  color: string;
}

export interface Reviewer {
  member: MemberRef;
  state: ReviewState;
}

export interface CheckDetail {
  name: string;
  status: CiStatus;
}

export interface PullRequest {
  num: number;
  title: string;
  branch: string | null;
  state: PrState;
  checks: CiStatus;
  checksDetail: CheckDetail[];
  additions: number;
  deletions: number;
  filesChanged: number;
  aiGenerated: boolean;
  reviewers: Reviewer[];
}

export interface FeatureRef {
  key: string;
  title: string;
  color?: string | null;
}

export interface Issue {
  key: string;
  type: IssueType;
  title: string;
  priority: number;
  status: Status;
  space: Space;
  points: number;
  assignee: MemberRef | null;
  owner: MemberRef | null;
  feature: FeatureRef | null;
  sprint: string | null;
  labels: Label[];
  branch: string | null;
  blocked: boolean;
  reviewRequested: boolean;
  commentCount: number;
  pr: PullRequest | null;
  product: string | null;
  component: string | null;
  taskId: string | null;
  targetRelease: string[];
  // monday.com two-way sync
  mondayItemId?: string | null;
  mondayBoardId?: string | null;
  mondaySyncedAt?: string | null;
  syncState?: 'synced' | 'pending' | 'error' | null;
  mondayStatus?: string | null;
  mondayStatusColor?: string | null;
}

export interface Comment {
  id: number;
  author: MemberRef;
  kind: 'comment' | 'commit' | 'ai';
  body: string;
  createdAt: string;
}

export interface CatalogItem {
  id: number;
  kind: 'product' | 'component' | 'release';
  name: string;
}

export interface CategoryValue {
  value: string;
  count: number;
}
export interface Categories {
  products: CategoryValue[];
  components: CategoryValue[];
}

export interface DescriptionBlock {
  type: 'heading' | 'paragraph' | 'list' | 'image' | 'link';
  text?: string;
  items?: string[];
  url?: string;
}

export interface RecapSection {
  heading: string;
  text: string;
}

export interface RecapAction {
  owner?: string;
  title: string;
  detail: string;
}

export interface MeetingNote {
  id: number;
  title: string;
  meetingDate: string | null;
  summary: string;
  sections: RecapSection[];
  actionItems: RecapAction[];
  attendees: string[];
  source: string;
  createdAt: string;
}

export interface RecapList {
  connected: boolean;
  source: string;
  recaps: MeetingNote[];
}

export interface RecapSyncResult {
  imported: number;
  recaps: MeetingNote[];
}

export interface ChildProgress {
  done: number;
  total: number;
}

export interface AuditEntry {
  id: number;
  actor: MemberRef | null;
  summary: string;
  createdAt: string;
}

export interface MondayField {
  title: string;
  value: string;
  type?: string | null;
  color?: string | null;
}

export interface IssueDetail extends Issue {
  description: DescriptionBlock[];
  comments: Comment[];
  prs: PullRequest[];
  auditLog: AuditEntry[];
  children?: Issue[] | null;
  childProgress?: ChildProgress | null;
  mondayFields?: MondayField[];
}

export interface BranchResponse {
  branch: string;
  issue: Issue;
}

// --- views ---
export interface Bootstrap {
  currentUser: Member;
  members: Member[];
  spaces: SpaceInfo[];
  sprints: Sprint[];
  labels: Record<string, string>;
}

export interface BoardColumn {
  key: Status;
  title: string;
  wipLimit: number;
  count: number;
  issues: Issue[];
}

export interface Board {
  columns: BoardColumn[];
}

export interface BacklogGroup {
  id: string;
  name: string;
  meta: string;
  active: boolean;
  capacity: number | null;
  points: number;
  count: number;
  issues: Issue[];
}

export interface Backlog {
  groups: BacklogGroup[];
}

export interface SprintHealth {
  committed: number;
  done: number;
  inProgress: number;
  review: number;
  todo: number;
  remaining: number;
  scopeAdded: number;
  onTrack: boolean;
}

export interface StatCard {
  label: string;
  value: string;
  unit: string;
  delta: string;
  good: boolean;
}

export interface Burndown {
  max: number;
  ideal: number[];
  actual: number[];
  days: string[];
}

export interface VelocityBar {
  sprint: string;
  committed: number;
  completed: number;
}

export interface DistributionSlice {
  status: Status;
  label: string;
  count: number;
}

export interface Reports {
  stats: StatCard[];
  burndown: Burndown;
  velocity: VelocityBar[];
  distribution: DistributionSlice[];
}

export interface TimelineMonth {
  label: string;
  startWeek: number;
  spanWeeks: number;
}

export interface TimelineRow {
  featureKey: string;
  name: string;
  color: string;
  startWeek: number;
  spanWeeks: number;
  progress: number;
}

export interface Timeline {
  months: TimelineMonth[];
  todayWeek: number;
  rows: TimelineRow[];
}

export interface RiskItem {
  issue: Issue;
  reason: string;
}

export interface WorkloadRow {
  member: MemberRef;
  points: number;
  overloaded: boolean;
}

export interface EpicProgressRow {
  key: string;
  title: string;
  color: string;
  done: number;
  total: number;
  progress: number;
}

export type ActionType =
  | 'ci_failing'
  | 'changes_requested'
  | 'review_request'
  | 'blocked'
  | 'monday_unsynced';

export interface ActionItem {
  kind: ActionType;
  issue: Issue;
  reason: string;
  severity: number;
}

export interface MondaySummary {
  pendingCount: number;
  lastSyncedAt: string | null;
}

export interface DashboardDeveloper {
  myFocus: Issue[];
  reviewQueue: Issue[];
  myPrs: Issue[];
  standup: string[];
  sprintHealth: SprintHealth;
  actionItems: ActionItem[];
  blocked: Issue[];
  failingCi: Issue[];
  monday: MondaySummary;
}

export interface DashboardPo {
  sprintHealth: SprintHealth;
  risks: RiskItem[];
  workload: WorkloadRow[];
  epicProgress: EpicProgressRow[];
  weeklyReport: string;
}

export interface Dashboard {
  role: Role;
  developer?: DashboardDeveloper;
  po?: DashboardPo;
}

// --- ai ---
export interface SuggestedResolution {
  summary: string;
  files: string[];
}

export interface SummarizeResponse {
  bullets: string[];
  suggestedResolution: SuggestedResolution;
}

export interface CreatePrResponse {
  pr: PullRequest;
  issue: IssueDetail;
}

export interface SolveResponse {
  pr: PullRequest;
  summary: string;
  files: string[];
  issue: IssueDetail;
}

export interface AssistantResponse {
  bullets: string[];
}

// --- inbox ---
export type EmailCategory =
  | 'customer'
  | 'internal'
  | 'notification'
  | 'newsletter'
  | 'alert'
  | 'meeting';
export type IgnoreField = 'sender' | 'domain' | 'category' | 'keyword';

export interface Email {
  id: number;
  senderName: string;
  senderEmail: string;
  senderColor: string;
  subject: string;
  preview: string;
  category: EmailCategory;
  labels: string[];
  receivedAt: string;
  unread: boolean;
  starred: boolean;
  ignored: boolean;
}

export interface EmailDetail extends Email {
  body: string;
}

export interface IgnoreRule {
  id: number;
  field: IgnoreField;
  value: string;
  active: boolean;
  matched: number;
}

export interface CategoryBucket {
  category: EmailCategory;
  label: string;
  count: number;
  color: string;
}

export interface Inbox {
  emails: Email[];
  categories: CategoryBucket[];
  unread: number;
  ignoredCount: number;
}

export interface RecapGroup {
  category: EmailCategory;
  label: string;
  headline: string;
  count: number;
}

export interface InboxRecap {
  bullets: string[];
  groups: RecapGroup[];
  ignoredCount: number;
  summarized: number;
}

// --- calendar ---
export interface Attendee {
  name: string;
  initials: string;
  color: string;
}

export interface MeetingRecap {
  id: number;
  summary: string;
  actionItems: string[];
  decisions: string[];
  source?: string; // 'zoom' (AI Companion) | 'cadence'
  createdAt: string;
}

export interface ZoomAccount {
  connected: boolean;
  accountName: string | null;
  connectedAt: string | null;
}

export interface YbugAccount {
  connected: boolean;
  projectName: string | null;
  connectedAt: string | null;
  ticketCount: number;
}

export interface YbugSyncResult {
  account: YbugAccount;
  created: number;
  keys: string[];
}

export interface CalendarEvent {
  id: number;
  title: string;
  start: string;
  end: string;
  attendees: Attendee[];
  meetLink: string | null;
  location: string | null;
  description: string;
  source: string;
  recap: MeetingRecap | null;
}

export interface CalendarAccount {
  connected: boolean;
  email: string | null;
  connectedAt: string | null;
}

export interface CalendarData {
  account: CalendarAccount;
  weekStart: string;
  weekEnd: string;
  events: CalendarEvent[];
}

export interface ConnectResult {
  account: CalendarAccount;
  imported: number;
}

export interface RecapResult {
  event: CalendarEvent;
  recap: MeetingRecap;
}

// --- github ---
export interface GitHubRepo {
  connected: boolean;
  owner: string | null;
  name: string | null;
  fullName: string | null;
  defaultBranch: string;
  connectedAt: string | null;
}

export interface RepoBranch {
  name: string;
  ahead: number;
  behind: number;
  lastCommit: string;
  author: MemberRef | null;
  updatedAt: string;
}

export interface RepoLinks {
  repo: GitHubRepo;
  key: string;
  branches: RepoBranch[];
  prs: PullRequest[];
}

export interface GitHubConnectResult {
  repo: GitHubRepo;
  branches: number;
  pullRequests: number;
}

// --- monday.com ---
export interface MondayOwner {
  name: string;
  initials: string;
  color: string;
}

export interface MondayColumn {
  title: string;
  value: string;
}

export interface MondayGroup {
  id: string;
  title: string;
}

export interface MondayItem {
  id: number;
  itemId: string;
  name: string;
  group: string;
  statusLabel: string | null;
  statusColor: string | null;
  owner: MondayOwner | null;
  url: string | null;
  updatedAt: string | null;
  columns: MondayColumn[];
  issueKey: string | null;
  imported: boolean;
}

export interface MondayBoard {
  id: number;
  boardId: string;
  name: string;
  description: string;
  kind: string;
  url: string | null;
  groups: MondayGroup[];
  itemCount: number;
  items: MondayItem[];
}

export interface MondayAccount {
  connected: boolean;
  accountName: string | null;
  connectedAt: string | null;
}

export interface MondayData {
  account: MondayAccount;
  boards: MondayBoard[];
}

export interface MondayConnectResult {
  account: MondayAccount;
  boards: number;
  items: number;
  imported?: number;
  pulled?: number;
  pushed?: number;
}

export interface MondayImportResult {
  item: MondayItem;
  issueKey: string;
}
