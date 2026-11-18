import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

const BASE = '/api/v1/reports';

export interface CycleReportText {
  cycle: number;
  text: string;
  whatsapp_url: string;
}

@Injectable({ providedIn: 'root' })
export class ReportService {
  private readonly http = inject(HttpClient);

  // Texte du bilan d'une bande + lien WhatsApp prêt à l'emploi (construit par le serveur).
  whatsapp(cycleId: number): Observable<CycleReportText> {
    return this.http.get<CycleReportText>(`${BASE}/${cycleId}/whatsapp/`);
  }

  pdf(cycleId: number): Observable<Blob> {
    return this.http.get(`${BASE}/${cycleId}/pdf/`, { responseType: 'blob' });
  }
}
