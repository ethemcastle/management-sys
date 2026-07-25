import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Email,
  EmailCategory,
  EmailDetail,
  IgnoreField,
  IgnoreRule,
  Inbox,
  InboxRecap,
} from '../models';

@Injectable({ providedIn: 'root' })
export class EmailsService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  inbox(category?: EmailCategory | null, includeIgnored = false): Observable<Inbox> {
    let p = new HttpParams();
    if (category) p = p.set('category', category);
    if (includeIgnored) p = p.set('includeIgnored', 'true');
    return this.http.get<Inbox>(`${this.base}/emails`, { params: p });
  }

  get(id: number): Observable<EmailDetail> {
    return this.http.get<EmailDetail>(`${this.base}/emails/${id}`);
  }

  patch(id: number, body: Partial<Pick<Email, 'unread' | 'starred'>>): Observable<Email> {
    return this.http.patch<Email>(`${this.base}/emails/${id}`, body);
  }

  recap(): Observable<InboxRecap> {
    return this.http.post<InboxRecap>(`${this.base}/emails/recap`, {});
  }

  listRules(): Observable<IgnoreRule[]> {
    return this.http.get<IgnoreRule[]>(`${this.base}/emails/ignore-rules`);
  }

  createRule(field: IgnoreField, value: string): Observable<IgnoreRule> {
    return this.http.post<IgnoreRule>(`${this.base}/emails/ignore-rules`, { field, value });
  }

  deleteRule(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/emails/ignore-rules/${id}`);
  }
}
