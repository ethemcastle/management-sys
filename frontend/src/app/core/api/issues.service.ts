import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  BranchResponse,
  Categories,
  Comment,
  Issue,
  IssueDetail,
  Space,
  Status,
} from '../models';

export interface IssueListParams {
  space?: Space;
  sprint?: string;
  assignee?: string;
  status?: Status;
  product?: string;
  component?: string;
  includeFeatures?: boolean;
}

export interface CreateIssueBody {
  type: Issue['type'];
  title: string;
  description?: string | null;
  priority?: number;
  status?: Status;
  space: Space;
  points?: number;
  assigneeInitials?: string | null;
  featureKey?: string | null;
  sprintId?: string | null;
  labels?: string[];
  product?: string | null;
  mondayBoardId?: string | null;
  mondayGroupId?: string | null;
}

export type PatchIssueBody = Partial<{
  status: Status;
  assigneeInitials: string | null;
  ownerInitials: string | null;
  priority: number;
  points: number;
  sprintId: string | null;
  featureKey: string | null;
  title: string;
  description: string | null;
  blocked: boolean;
  product: string | null;
  component: string | null;
  taskId: string | null;
  targetRelease: string[];
}>;

@Injectable({ providedIn: 'root' })
export class IssuesService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  list(params: IssueListParams = {}): Observable<Issue[]> {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) p = p.set(k, String(v));
    }
    return this.http.get<Issue[]>(`${this.base}/issues`, { params: p });
  }

  get(key: string): Observable<IssueDetail> {
    return this.http.get<IssueDetail>(`${this.base}/issues/${key}`);
  }

  /** Distinct Product/Component values (with counts) for the sidebar sections. */
  categories(): Observable<Categories> {
    return this.http.get<Categories>(`${this.base}/issues/categories`);
  }

  create(body: CreateIssueBody): Observable<Issue> {
    return this.http.post<Issue>(`${this.base}/issues`, body);
  }

  patch(key: string, body: PatchIssueBody): Observable<Issue> {
    return this.http.patch<Issue>(`${this.base}/issues/${key}`, body);
  }

  createBranch(key: string): Observable<BranchResponse> {
    return this.http.post<BranchResponse>(`${this.base}/issues/${key}/branch`, {});
  }

  addComment(key: string, body: string): Observable<Comment> {
    return this.http.post<Comment>(`${this.base}/issues/${key}/comments`, { body });
  }

  delete(key: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/issues/${key}`);
  }

  /** Clear all tickets (keeps members/sprints/catalog/connection). */
  clearDemo(): Observable<{ deleted: number }> {
    return this.http.post<{ deleted: number }>(`${this.base}/admin/reset-issues`, {});
  }
}
