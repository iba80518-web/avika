import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { EggCollection, EggCollectionChanges, EggSummary, NewEggCollection } from './egg.models';
import { Page } from './farming.models';

@Injectable({ providedIn: 'root' })
export class EggService {
  private readonly http = inject(HttpClient);

  list(cycleId?: number): Observable<Page<EggCollection>> {
    let params = new HttpParams();
    if (cycleId !== undefined) params = params.set('cycle', cycleId);
    return this.http.get<Page<EggCollection>>(`${API_BASE}/egg-collections/`, { params });
  }

  // Stock d'œufs et totaux des 30 derniers jours, avec le taux de ponte de chaque jour.
  summary(cycleId: number): Observable<EggSummary> {
    return this.http.get<EggSummary>(`${API_BASE}/egg-collections/summary/`, {
      params: new HttpParams().set('cycle', cycleId),
    });
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais un second ramassage.
  create(body: NewEggCollection): Observable<EggCollection> {
    return this.http.post<EggCollection>(`${API_BASE}/egg-collections/`, body);
  }

  update(id: number, body: EggCollectionChanges): Observable<EggCollection> {
    return this.http.patch<EggCollection>(`${API_BASE}/egg-collections/${id}/`, body);
  }
}
