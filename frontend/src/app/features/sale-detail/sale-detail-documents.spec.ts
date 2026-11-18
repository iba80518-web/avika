import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { SaleDetail } from './sale-detail';

const SALE = {
  id: 1, uuid: 'u1', customer: 5, customer_name: 'Boucherie Diallo', cycle: 2, sale_date: '2026-11-07',
  sale_type: 'count', quantity: 100, weight_kg: null, unit_price: 40000, total_amount: 4000000,
  paid: 2500000, balance: 1500000, status: 'active', note: '', created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const PAYMENT = {
  id: 4, uuid: 'p', sale: 1, amount: 2500000, payment_date: '2026-11-07', method: 'cash',
  created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const DOCUMENT = {
  id: 9, uuid: 'd9', kind: 'invoice', number: 'FAC-2026-0001', year: 2026, sequence: 1, sale: 1, payment: null,
  issued_on: '2026-11-18', customer_name: 'Boucherie Diallo', sale_status: 'active', content: {},
  pdf_url: '/api/v1/documents/9/pdf/', created_by: 3, created_at: '2026-11-18T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('SaleDetail : factures et reçus', () => {
  let fixture: ComponentFixture<SaleDetail>;
  let root: HTMLElement;
  let http: HttpTestingController;
  let downloads: ReturnType<typeof vi.spyOn>;
  const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };

  async function open(sale: object = SALE, payments: unknown[] = [PAYMENT]): Promise<void> {
    fixture.detectChanges();
    http.expectOne('/api/v1/sales/1/').flush(sale);
    http.expectOne('/api/v1/sales/1/payments/').flush(payments);
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  }

  const button = (label: string): HTMLButtonElement =>
    Array.from(root.querySelectorAll('button')).find((item) =>
      item.textContent?.trim().startsWith(label),
    ) as HTMLButtonElement;

  beforeEach(async () => {
    Object.assign(URL, { createObjectURL: () => 'blob:test', revokeObjectURL: () => undefined });
    downloads = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    await TestBed.configureTestingModule({
      imports: [SaleDetail],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: '1' }) } } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SaleDetail);
    root = fixture.nativeElement as HTMLElement;
  });

  afterEach(() => {
    http.verify();
    downloads.mockRestore();
    Object.assign(URL, { createObjectURL: original.create, revokeObjectURL: original.revoke });
  });

  async function finishDownload(): Promise<void> {
    await tick();
    http
      .expectOne((request) => request.url.endsWith('/pdf/'))
      .flush(new Blob(['%PDF'], { type: 'application/pdf' }));
    await tick();
  }

  it('télécharge la facture d’une vente avec client enregistré, sans envoyer de nom', async () => {
    await open();
    expect(root.textContent).toContain('figurent sur les documents');
    expect(root.querySelector('#guest-name')).toBeNull();
    button('Télécharger la facture').click();
    const issue = http.expectOne('/api/v1/documents/');
    expect(issue.request.method).toBe('POST');
    expect(issue.request.body).toEqual({ kind: 'invoice', sale: 1 });
    issue.flush(DOCUMENT);
    await finishDownload();
    expect(downloads).toHaveBeenCalledTimes(1);
  });

  it('envoie le nom saisi pour une vente de passage', async () => {
    await open({ ...SALE, customer: null, customer_name: null, balance: 0, paid: 4000000 });
    const input = root.querySelector<HTMLInputElement>('#guest-name') as HTMLInputElement;
    input.value = 'Awa Camara';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    button('Télécharger la facture').click();
    const issue = http.expectOne('/api/v1/documents/');
    expect(issue.request.body).toEqual({ kind: 'invoice', sale: 1, customer_name: 'Awa Camara' });
    issue.flush(DOCUMENT);
    await finishDownload();
  });

  it('émet le reçu du paiement choisi', async () => {
    await open();
    button('Reçu').click();
    const issue = http.expectOne('/api/v1/documents/');
    expect(issue.request.body).toEqual({ kind: 'receipt', payment: 4 });
    issue.flush({ ...DOCUMENT, kind: 'receipt', number: 'REC-2026-0001', payment: 4 });
    await finishDownload();
    expect(downloads).toHaveBeenCalledTimes(1);
  });

  it('explique qu’il faut du réseau, sans appeler le serveur', async () => {
    await open();
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
    try {
      button('Télécharger la facture').click();
      await tick();
      fixture.detectChanges();
      expect(root.textContent).toContain('Pas de connexion');
      http.expectNone('/api/v1/documents/');
    } finally {
      delete (navigator as unknown as Record<string, unknown>)['onLine'];
    }
  });

  it('montre l’erreur du serveur et laisse réessayer', async () => {
    await open();
    button('Télécharger la facture').click();
    http.expectOne('/api/v1/documents/').flush({ detail: 'Indisponible.' }, { status: 500, statusText: 'x' });
    await tick();
    fixture.detectChanges();
    expect(root.querySelector('.form-error')).not.toBeNull();
    expect(button('Télécharger la facture').disabled).toBe(false);
  });

  it('n’offre pas de facture pour une vente annulée', async () => {
    await open({ ...SALE, status: 'cancelled' });
    expect(button('Télécharger la facture')).toBeUndefined();
  });
});
