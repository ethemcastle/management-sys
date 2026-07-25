import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { GitHubConnectResult, GitHubRepo, RepoLinks } from '../models';

@Injectable({ providedIn: 'root' })
export class GithubService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  repo(): Observable<GitHubRepo> {
    return this.http.get<GitHubRepo>(`${this.base}/github/repo`);
  }

  connect(fullName: string): Observable<GitHubConnectResult> {
    return this.http.post<GitHubConnectResult>(`${this.base}/github/connect`, { fullName });
  }

  sync(): Observable<GitHubConnectResult> {
    return this.http.post<GitHubConnectResult>(`${this.base}/github/sync`, {});
  }

  disconnect(): Observable<GitHubRepo> {
    return this.http.post<GitHubRepo>(`${this.base}/github/disconnect`, {});
  }

  links(key: string): Observable<RepoLinks> {
    return this.http.get<RepoLinks>(`${this.base}/github/issues/${key}/links`);
  }
}
