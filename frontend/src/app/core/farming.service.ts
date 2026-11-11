import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import {
  Coop,
  Cycle,
  CycleSummary,
  FlockEvent,
  NewMortality,
  Page,
} from './farming.models';

@Injectable({ providedIn: 'root' })
export class FarmingService {
  private readonly http = inject(HttpClient);

  cycles(): Observable<Page<Cycle>> {
    return this.http.get<Page<Cycle>>(`${API_BASE}/cycles/`);
  }

  cycle(id: number): Observable<Cycle> {
    return this.http.get<Cycle>(`${API_BASE}/cycles/${id}/`);
  }

  summary(id: number): Observable<CycleSummary> {
    return this.http.get<CycleSummary>(`${API_BASE}/cycles/${id}/summary/`);
  }

  events(id: number): Observable<Page<FlockEvent>> {
    return this.http.get<Page<FlockEvent>>(`${API_BASE}/cycles/${id}/events/`);
  }

  coops(): Observable<Page<Coop>> {
    return this.http.get<Page<Coop>>(`${API_BASE}/coops/`);
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais de doublon (201 la première fois, 200 ensuite).
  recordMortality(cycleId: number, body: NewMortality): Observable<FlockEvent> {
    return this.http.post<FlockEvent>(`${API_BASE}/cycles/${cycleId}/events/`, body);
  }
}
