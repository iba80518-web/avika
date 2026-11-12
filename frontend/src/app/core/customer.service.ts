import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Customer } from './finance.models';

export const CUSTOMER_TYPES: { value: string; label: string }[] = [
  { value: 'individual', label: 'Particulier' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'hotel', label: 'Hôtel' },
  { value: 'wholesaler', label: 'Grossiste' },
  { value: 'reseller', label: 'Revendeur' },
  { value: 'other', label: 'Autre' },
];

export interface NewCustomer {
  name: string;
  phone: string;
  customer_type: string;
}

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private readonly http = inject(HttpClient);

  create(body: NewCustomer): Observable<Customer> {
    return this.http.post<Customer>(`${API_BASE}/customers/`, body);
  }
}
