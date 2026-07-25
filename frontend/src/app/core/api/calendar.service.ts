import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CalendarAccount, CalendarData, ConnectResult, Issue, RecapResult } from '../models';

@Injectable({ providedIn: 'root' })
export class CalendarService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  /** `week` is the Monday of the week to show (YYYY-MM-DD); omit for the current week. */
  get(week?: string): Observable<CalendarData> {
    let params = new HttpParams();
    if (week) params = params.set('week', week);
    return this.http.get<CalendarData>(`${this.base}/calendar`, { params });
  }

  connect(): Observable<ConnectResult> {
    return this.http.post<ConnectResult>(`${this.base}/calendar/connect`, {});
  }

  disconnect(): Observable<CalendarAccount> {
    return this.http.post<CalendarAccount>(`${this.base}/calendar/disconnect`, {});
  }

  recapEvent(id: number): Observable<RecapResult> {
    return this.http.post<RecapResult>(`${this.base}/calendar/events/${id}/recap`, {});
  }

  /** Turn a recap's next-step (action item) into a Cadence ticket. */
  actionItemToTicket(recapId: number, index: number): Observable<Issue> {
    return this.http.post<Issue>(`${this.base}/calendar/recaps/${recapId}/action-item`, { index });
  }
}
