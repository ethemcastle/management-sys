import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Backlog,
  Board,
  Dashboard,
  Reports,
  Role,
  Space,
  Sprint,
  SprintHealth,
  Timeline,
} from '../models';

/** Server-computed view endpoints (board, backlog, reports, timeline, dashboards). */
@Injectable({ providedIn: 'root' })
export class ViewsService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  board(space: Space, sprint?: string): Observable<Board> {
    let p = new HttpParams().set('space', space);
    if (sprint) p = p.set('sprint', sprint);
    return this.http.get<Board>(`${this.base}/board`, { params: p });
  }

  backlog(space: Space): Observable<Backlog> {
    return this.http.get<Backlog>(`${this.base}/backlog`, {
      params: new HttpParams().set('space', space),
    });
  }

  sprintHealth(sprintId: string, space: Space): Observable<SprintHealth> {
    return this.http.get<SprintHealth>(`${this.base}/sprints/${sprintId}/health`, {
      params: new HttpParams().set('space', space),
    });
  }

  startSprint(sprintId: string): Observable<Sprint> {
    return this.http.post<Sprint>(`${this.base}/sprints/${sprintId}/start`, {});
  }

  reports(space: Space, sprint?: string): Observable<Reports> {
    let p = new HttpParams().set('space', space);
    if (sprint) p = p.set('sprint', sprint);
    return this.http.get<Reports>(`${this.base}/reports`, { params: p });
  }

  timeline(space: Space): Observable<Timeline> {
    return this.http.get<Timeline>(`${this.base}/timeline`, {
      params: new HttpParams().set('space', space),
    });
  }

  dashboard(role: Role, space: Space): Observable<Dashboard> {
    const p = new HttpParams().set('role', role).set('space', space);
    return this.http.get<Dashboard>(`${this.base}/dashboard`, { params: p });
  }
}
