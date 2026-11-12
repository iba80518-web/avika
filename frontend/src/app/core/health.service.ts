import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Page } from './farming.models';
import {
  CompleteTask,
  HealthStatus,
  HealthTask,
  HealthTemplate,
  NewHealthTask,
  Reminders,
  ScheduleRequest,
} from './health.models';

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  tasks(status?: HealthStatus): Observable<Page<HealthTask>> {
    const query = status ? `?status=${status}` : '';
    return this.http.get<Page<HealthTask>>(`${API_BASE}/health-tasks/${query}`);
  }

  reminders(): Observable<Reminders> {
    return this.http.get<Reminders>(`${API_BASE}/health-tasks/reminders/`);
  }

  templates(): Observable<Page<HealthTemplate>> {
    return this.http.get<Page<HealthTemplate>>(`${API_BASE}/health-templates/`);
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais une seconde tâche.
  createTask(body: NewHealthTask): Observable<HealthTask> {
    return this.http.post<HealthTask>(`${API_BASE}/health-tasks/`, body);
  }

  // Crée les tâches d'un calendrier type pour une bande. Relancer ne crée pas de doublon.
  schedule(body: ScheduleRequest): Observable<HealthTask[]> {
    return this.http.post<HealthTask[]>(`${API_BASE}/health-tasks/schedule/`, body);
  }

  complete(id: number, body: CompleteTask): Observable<HealthTask> {
    return this.http.post<HealthTask>(`${API_BASE}/health-tasks/${id}/complete/`, body);
  }

  cancel(id: number): Observable<HealthTask> {
    return this.http.post<HealthTask>(`${API_BASE}/health-tasks/${id}/cancel/`, {});
  }
}
