import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Issue, YbugAccount, YbugSyncResult } from '../models';

@Injectable({ providedIn: 'root' })
export class YbugService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  get(): Observable<YbugAccount> {
    return this.http.get<YbugAccount>(`${this.base}/ybug`);
  }
  connect(): Observable<YbugAccount> {
    return this.http.post<YbugAccount>(`${this.base}/ybug/connect`, {});
  }
  disconnect(): Observable<YbugAccount> {
    return this.http.post<YbugAccount>(`${this.base}/ybug/disconnect`, {});
  }
  sync(): Observable<YbugSyncResult> {
    return this.http.post<YbugSyncResult>(`${this.base}/ybug/sync`, {});
  }
  /** Create one demo feedback ticket (as if a tester filed it in Ybug). */
  simulate(): Observable<Issue> {
    return this.http.post<Issue>(`${this.base}/ybug/simulate`, {});
  }
}
