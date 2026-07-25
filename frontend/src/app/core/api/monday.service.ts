import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  MondayAccount,
  MondayConnectResult,
  MondayData,
  MondayImportResult,
} from '../models';

@Injectable({ providedIn: 'root' })
export class MondayService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  get(): Observable<MondayData> {
    return this.http.get<MondayData>(`${this.base}/monday`);
  }

  connect(): Observable<MondayConnectResult> {
    return this.http.post<MondayConnectResult>(`${this.base}/monday/connect`, {});
  }

  sync(): Observable<MondayConnectResult> {
    return this.http.post<MondayConnectResult>(`${this.base}/monday/sync`, {});
  }

  disconnect(): Observable<MondayAccount> {
    return this.http.post<MondayAccount>(`${this.base}/monday/disconnect`, {});
  }

  /** Create a real risr/crm ticket from a monday item. */
  importItem(id: number): Observable<MondayImportResult> {
    return this.http.post<MondayImportResult>(`${this.base}/monday/items/${id}/import`, {});
  }
}
