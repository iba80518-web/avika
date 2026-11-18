import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DocumentService } from './documents.service';

describe('DocumentService', () => {
  let service: DocumentService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DocumentService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lit les paramètres', () => {
    service.settings().subscribe();
    const request = http.expectOne('/api/v1/document-settings/');
    expect(request.request.method).toBe('GET');
    request.flush({});
  });

  it('modifie seulement les champs envoyés', () => {
    service.updateSettings({ business_name: 'Ferme du Soleil', accent_color: '#B22222' }).subscribe();
    const request = http.expectOne('/api/v1/document-settings/');
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body).toEqual({ business_name: 'Ferme du Soleil', accent_color: '#B22222' });
    request.flush({});
  });

  it('envoie le logo dans le champ « image » du formulaire', () => {
    service.uploadLogo(new Blob(['x'], { type: 'image/png' })).subscribe();
    const request = http.expectOne('/api/v1/document-settings/logo/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBe(true);
    expect((request.request.body as FormData).get('image') instanceof Blob).toBe(true);
    request.flush({});
  });

  it('retire le logo', () => {
    service.deleteLogo().subscribe();
    const request = http.expectOne('/api/v1/document-settings/logo/');
    expect(request.request.method).toBe('DELETE');
    request.flush({});
  });

  it('lit le logo protégé sous forme de blob', () => {
    service.logoFile().subscribe();
    const request = http.expectOne('/api/v1/document-settings/logo/file/');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['x']));
  });

  it('liste les documents d’une vente', () => {
    service.list({ sale: 12 }).subscribe();
    const request = http.expectOne((item) => item.url === '/api/v1/documents/');
    expect(request.request.params.get('sale')).toBe('12');
    request.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('émet une facture avec le nom saisi', () => {
    service.issue({ kind: 'invoice', sale: 12, customer_name: 'Fatou Barry' }).subscribe();
    const request = http.expectOne('/api/v1/documents/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ kind: 'invoice', sale: 12, customer_name: 'Fatou Barry' });
    request.flush({});
  });

  it('émet un reçu pour un paiement', () => {
    service.issue({ kind: 'receipt', payment: 5 }).subscribe();
    const request = http.expectOne('/api/v1/documents/');
    expect(request.request.body).toEqual({ kind: 'receipt', payment: 5 });
    request.flush({});
  });

  it('télécharge le PDF protégé sous forme de blob', () => {
    service.pdf({ pdf_url: '/api/v1/documents/7/pdf/' }).subscribe();
    const request = http.expectOne('/api/v1/documents/7/pdf/');
    expect(request.request.method).toBe('GET');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['%PDF']));
  });
});
