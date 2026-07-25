import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CatalogItem } from '../models';

/** Manage the option lists (Products, Components, Releases) behind ticket fields. */
@Injectable({ providedIn: 'root' })
export class CatalogService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  list(kind?: CatalogItem['kind']): Observable<CatalogItem[]> {
    let p = new HttpParams();
    if (kind) p = p.set('kind', kind);
    return this.http.get<CatalogItem[]>(`${this.base}/catalog`, { params: p });
  }
  create(kind: CatalogItem['kind'], name: string): Observable<CatalogItem> {
    return this.http.post<CatalogItem>(`${this.base}/catalog`, { kind, name });
  }
  rename(id: number, name: string): Observable<CatalogItem> {
    return this.http.patch<CatalogItem>(`${this.base}/catalog/${id}`, { name });
  }
  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/catalog/${id}`);
  }
}
