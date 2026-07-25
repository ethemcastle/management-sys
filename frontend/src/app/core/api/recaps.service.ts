import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Issue, RecapList, RecapSyncResult } from '../models';

@Injectable({ providedIn: 'root' })
export class RecapsService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  list(): Observable<RecapList> {
    return this.http.get<RecapList>(`${this.base}/recaps`);
  }
  sync(): Observable<RecapSyncResult> {
    return this.http.post<RecapSyncResult>(`${this.base}/recaps/sync`, {});
  }
  /** Turn the Nth next-step of a recap into a risr/crm ticket. */
  actionItem(recapId: number, index: number): Observable<Issue> {
    return this.http.post<Issue>(`${this.base}/recaps/${recapId}/action-item`, { index });
  }
  /** Turn every next-step of a recap into an assigned ticket. */
  createAll(recapId: number): Observable<Issue[]> {
    return this.http.post<Issue[]>(`${this.base}/recaps/${recapId}/tickets`, {});
  }
}
