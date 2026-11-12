import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SaleForm } from './sale-form';

const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const NEW_CUSTOMER = {
  id: 8, name: 'Hôtel Kaloum', phone: '', address: '', customer_type: 'individual', is_active: true,
  created_at: '2026-11-12T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('SaleForm — nouveau client', () => {
  let fixture: ComponentFixture<SaleForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SaleForm],
      providers: [provideRouter([{ path: 'ventes/:id', children: [] }]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SaleForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    http.expectOne('/api/v1/customers/').flush(page([]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function click(label: string): void {
    const button = Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  it('crée un client sans quitter la vente, puis le rattache à une vente à crédit', async () => {
    click('Nouveau client');
    fill('newName', 'Hôtel Kaloum');
    click('Créer le client');
    const created = http.expectOne('/api/v1/customers/');
    expect(created.request.method).toBe('POST');
    expect(created.request.body).toEqual({ name: 'Hôtel Kaloum', phone: '', customer_type: 'individual' });
    created.flush(NEW_CUSTOMER, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('#customer')?.textContent).toContain('Hôtel Kaloum');

    const select = root.querySelector<HTMLSelectElement>('#cycle') as HTMLSelectElement;
    select.value = '2';
    select.dispatchEvent(new Event('change'));
    fill('qty', '100');
    fill('price', '25000');
    fill('paid', '0');
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const sale = http.expectOne('/api/v1/sales/');
    expect(sale.request.body.customer).toBe(8);
    expect(sale.request.body.paid_amount).toBe(0);
    sale.flush({ id: 7 }, { status: 201, statusText: 'Created' });
  });

  it('affiche le refus du serveur quand le client existe déjà', async () => {
    click('Nouveau client');
    fill('newName', 'Hôtel Kaloum');
    click('Créer le client');
    http
      .expectOne('/api/v1/customers/')
      .flush({ name: ['Un client porte déjà ce nom.'] }, { status: 400, statusText: 'Bad Request' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('.newcustomer [role="alert"]')?.textContent).toContain('déjà ce nom');
  });
});
