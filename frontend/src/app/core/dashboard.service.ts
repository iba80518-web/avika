import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { DashboardData } from './dashboard.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  load(): Observable<DashboardData> {
    return this.http.get<DashboardData>(`${API_BASE}/dashboard/`);
  }
}
