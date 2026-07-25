import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Bootstrap } from '../models';

@Injectable({ providedIn: 'root' })
export class BootstrapService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  get(): Observable<Bootstrap> {
    return this.http.get<Bootstrap>(`${this.base}/bootstrap`);
  }
}
