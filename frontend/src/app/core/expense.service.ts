import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Expense, ExpenseChanges, NewExpense } from './expense.models';
import { Page } from './farming.models';

@Injectable({ providedIn: 'root' })
export class ExpenseService {
  private readonly http = inject(HttpClient);

  list(): Observable<Page<Expense>> {
    return this.http.get<Page<Expense>>(`${API_BASE}/expenses/`);
  }

  get(id: number): Observable<Expense> {
    return this.http.get<Expense>(`${API_BASE}/expenses/${id}/`);
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais une seconde dépense.
  create(body: NewExpense): Observable<Expense> {
    return this.http.post<Expense>(`${API_BASE}/expenses/`, body);
  }

  update(id: number, body: ExpenseChanges): Observable<Expense> {
    return this.http.patch<Expense>(`${API_BASE}/expenses/${id}/`, body);
  }
}
