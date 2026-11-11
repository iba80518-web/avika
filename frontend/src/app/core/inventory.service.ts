import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Page } from './farming.models';
import { NewMovement, NewProduct, Product, StockMovement } from './inventory.models';

@Injectable({ providedIn: 'root' })
export class InventoryService {
  private readonly http = inject(HttpClient);

  products(): Observable<Page<Product>> {
    return this.http.get<Page<Product>>(`${API_BASE}/products/`);
  }

  product(id: number): Observable<Product> {
    return this.http.get<Product>(`${API_BASE}/products/${id}/`);
  }

  movements(id: number): Observable<Page<StockMovement>> {
    return this.http.get<Page<StockMovement>>(`${API_BASE}/products/${id}/movements/`);
  }

  createProduct(body: NewProduct): Observable<Product> {
    return this.http.post<Product>(`${API_BASE}/products/`, body);
  }

  // Le uuid rend l'envoi sûr : le renvoyer ne crée jamais de doublon (201 la première fois, 200 ensuite).
  recordMovement(id: number, body: NewMovement): Observable<StockMovement> {
    return this.http.post<StockMovement>(`${API_BASE}/products/${id}/movements/`, body);
  }
}
