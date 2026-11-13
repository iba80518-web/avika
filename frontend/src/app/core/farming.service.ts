import { HttpClient } from '@angular/common/http';
import { Injectable, Injector, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { OutboxService, SubmitResult } from './outbox.service';
import {
  Coop,
  Cycle,
  CycleSummary,
  Farm,
  FlockEvent,
  NewCoop,
  NewCycle,
  NewMortality,
  Page,
} from './farming.models';

@Injectable({ providedIn: 'root' })
export class FarmingService {
  private readonly http = inject(HttpClient);
  private readonly injector = inject(Injector);

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

  farms(): Observable<Page<Farm>> {
    return this.http.get<Page<Farm>>(`${API_BASE}/farms/`);
  }

  createFarm(body: { name: string }): Observable<Farm> {
    return this.http.post<Farm>(`${API_BASE}/farms/`, body);
  }

  createCoop(body: NewCoop): Observable<Coop> {
    return this.http.post<Coop>(`${API_BASE}/coops/`, body);
  }

  createCycle(body: NewCycle): Observable<Cycle> {
    return this.http.post<Cycle>(`${API_BASE}/cycles/`, body);
  }

  // Le serveur n'accepte de dépasser la capacité du poulailler que si on le confirme explicitement.
  startCycle(id: number, confirmOverCapacity: boolean): Observable<Cycle> {
    const body = confirmOverCapacity ? { confirm_over_capacity: true } : {};
    return this.http.post<Cycle>(`${API_BASE}/cycles/${id}/start/`, body);
  }

  completeCycle(id: number): Observable<Cycle> {
    return this.http.post<Cycle>(`${API_BASE}/cycles/${id}/complete/`, {});
  }

  cancelCycle(id: number): Observable<Cycle> {
    return this.http.post<Cycle>(`${API_BASE}/cycles/${id}/cancel/`, {});
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais de doublon (201 la première fois, 200 ensuite).
  recordMortality(cycleId: number, body: NewMortality): Observable<FlockEvent> {
    return this.http.post<FlockEvent>(`${API_BASE}/cycles/${cycleId}/events/`, body);
  }

  // Sans réseau, la saisie est gardée sur le téléphone et envoyée plus tard (voir OutboxService).
  // Le service d'envoi n'est demandé qu'ici : les autres écrans n'en dépendent pas.
  submitMortality(
    cycleId: number,
    body: NewMortality,
    label: string,
  ): Observable<SubmitResult<FlockEvent>> {
    return this.injector
      .get(OutboxService)
      .submit<FlockEvent>(label, `${API_BASE}/cycles/${cycleId}/events/`, body, body.uuid ?? '');
  }
}
