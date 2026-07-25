import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ZoomAccount } from '../models';

@Injectable({ providedIn: 'root' })
export class ZoomService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  get(): Observable<ZoomAccount> {
    return this.http.get<ZoomAccount>(`${this.base}/zoom`);
  }

  connect(): Observable<ZoomAccount> {
    return this.http.post<ZoomAccount>(`${this.base}/zoom/connect`, {});
  }

  disconnect(): Observable<ZoomAccount> {
    return this.http.post<ZoomAccount>(`${this.base}/zoom/disconnect`, {});
  }
}
