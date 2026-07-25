import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AssistantResponse,
  Comment,
  CreatePrResponse,
  Space,
  SolveResponse,
  SummarizeResponse,
} from '../models';

export interface AssistantContext {
  view: string;
  space: Space;
  sprint?: string;
}

@Injectable({ providedIn: 'root' })
export class AiApiService {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  summarize(key: string): Observable<SummarizeResponse> {
    return this.http.post<SummarizeResponse>(`${this.base}/ai/issues/${key}/summarize`, {});
  }

  createPr(key: string): Observable<CreatePrResponse> {
    return this.http.post<CreatePrResponse>(`${this.base}/ai/issues/${key}/create-pr`, {});
  }

  solveTicket(key: string): Observable<SolveResponse> {
    return this.http.post<SolveResponse>(`${this.base}/ai/tickets/${key}/solve`, {});
  }

  assistant(question: string, context: AssistantContext): Observable<AssistantResponse> {
    return this.http.post<AssistantResponse>(`${this.base}/ai/assistant`, { question, context });
  }

  /** Ask the AI a question from a ticket comment; it researches the code and replies. */
  answer(key: string, question: string): Observable<Comment> {
    return this.http.post<Comment>(`${this.base}/ai/issues/${key}/answer`, { question });
  }
}
