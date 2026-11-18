import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import {
  DocumentSettings,
  DocumentSettingsChanges,
  IssuedDocument,
  NewDocument,
} from './documents.models';
import { Page } from './farming.models';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly http = inject(HttpClient);

  settings(): Observable<DocumentSettings> {
    return this.http.get<DocumentSettings>(`${API_BASE}/document-settings/`);
  }

  updateSettings(changes: DocumentSettingsChanges): Observable<DocumentSettings> {
    return this.http.patch<DocumentSettings>(`${API_BASE}/document-settings/`, changes);
  }

  // Envoi en formulaire avec fichier : aucun en-tête « Content-Type » à fixer (le navigateur s'en charge).
  uploadLogo(file: Blob, filename = 'logo.png'): Observable<DocumentSettings> {
    const form = new FormData();
    form.append('image', file, filename);
    return this.http.post<DocumentSettings>(`${API_BASE}/document-settings/logo/`, form);
  }

  deleteLogo(): Observable<DocumentSettings> {
    return this.http.delete<DocumentSettings>(`${API_BASE}/document-settings/logo/`);
  }

  // Le logo est protégé : on le lit avec la connexion de l'utilisateur, sous forme de blob.
  logoFile(): Observable<Blob> {
    return this.http.get(`${API_BASE}/document-settings/logo/file/`, { responseType: 'blob' });
  }

  list(filters: { sale?: number } = {}): Observable<Page<IssuedDocument>> {
    let params = new HttpParams();
    if (filters.sale !== undefined) params = params.set('sale', filters.sale);
    return this.http.get<Page<IssuedDocument>>(`${API_BASE}/documents/`, { params });
  }

  // Émet (ou renvoie, s'il existe déjà) la facture d'une vente ou le reçu d'un paiement.
  issue(body: NewDocument): Observable<IssuedDocument> {
    return this.http.post<IssuedDocument>(`${API_BASE}/documents/`, body);
  }

  // Le PDF est protégé : lu avec la connexion de l'utilisateur, sous forme de blob.
  pdf(document: Pick<IssuedDocument, 'pdf_url'>): Observable<Blob> {
    return this.http.get(document.pdf_url, { responseType: 'blob' });
  }
}
