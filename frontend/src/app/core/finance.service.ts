import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Page } from './farming.models';
import { Customer, NewPayment, NewSale, Receivable, Sale, SalePayment } from './finance.models';

@Injectable({ providedIn: 'root' })
export class FinanceService {
  private readonly http = inject(HttpClient);

  sales(): Observable<Page<Sale>> {
    return this.http.get<Page<Sale>>(`${API_BASE}/sales/`);
  }

  sale(id: number): Observable<Sale> {
    return this.http.get<Sale>(`${API_BASE}/sales/${id}/`);
  }

  payments(id: number): Observable<SalePayment[]> {
    return this.http.get<SalePayment[]>(`${API_BASE}/sales/${id}/payments/`);
  }

  customers(): Observable<Page<Customer>> {
    return this.http.get<Page<Customer>>(`${API_BASE}/customers/`);
  }

  receivables(): Observable<Receivable[]> {
    return this.http.get<Receivable[]>(`${API_BASE}/sales/receivables/`);
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais une seconde vente.
  recordSale(body: NewSale): Observable<Sale> {
    return this.http.post<Sale>(`${API_BASE}/sales/`, body);
  }

  recordPayment(id: number, body: NewPayment): Observable<SalePayment> {
    return this.http.post<SalePayment>(`${API_BASE}/sales/${id}/payments/`, body);
  }

  cancelSale(id: number, reason: string): Observable<Sale> {
    return this.http.post<Sale>(`${API_BASE}/sales/${id}/cancel/`, { reason });
  }
}
