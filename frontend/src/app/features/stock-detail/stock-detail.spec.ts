import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';

import { StockDetail } from './stock-detail';

const PRODUCT = {
  id: 1, name: 'Aliment démarrage', product_type: 'feed', base_unit: 'kg', low_stock_threshold: '100.000',
  is_active: true, stock: '70.000', stock_value: 140000, is_low: true, created_at: '2026-11-10T00:00:00Z',
};
const MOVEMENT = {
  id: 3, uuid: 'u', movement_type: 'exit', base_quantity: '380.000', total_cost: 760000,
  movement_date: '2026-11-07', cycle: 2, note: '', created_by: 3, created_at: '2026-11-10T00:00:00Z',
};
const CYCLE = {
  id: 2, coop: 2, name: 'Bande B', type: 'broiler', start_date: '2026-10-29', end_date: null,
  initial_count: 500, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 430, created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('StockDetail', () => {
  let fixture: ComponentFixture<StockDetail>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StockDetail],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: '1' }) } } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(StockDetail);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/products/1/').flush(PRODUCT);
    http.expectOne('/api/v1/products/1/movements/').flush(page([MOVEMENT]));
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
  }

  function pick(label: string): void {
    const button = Array.from(root.querySelectorAll<HTMLButtonElement>('.seg button')).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('affiche le niveau, le stock bas et l’historique avec le nom de la bande', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Aliment démarrage');
    expect(text).toContain('Stock bas');
    expect(text).toContain('Bande B');
    expect(text).toContain('−380');
  });

  it('refuse de sortir plus que le stock, sans contacter le serveur', async () => {
    fill('qty', '500');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/products/1/movements/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Stock insuffisant');
  });

  it('exige le coût d’une entrée', async () => {
    pick('Entrée');
    fill('qty', '50');
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('coût total');
  });

  it('enregistre une entrée avec son coût puis relit le stock', async () => {
    pick('Entrée');
    fill('qty', '50,5');
    fill('cost', '100000');
    submit();
    const request = http.expectOne('/api/v1/products/1/movements/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.movement_type).toBe('entry');
    expect(request.request.body.quantity).toBe(50.5);
    expect(request.request.body.total_cost).toBe(100000);
    expect(request.request.body.uuid).toBeTruthy();
    request.flush({ ...MOVEMENT, id: 9, movement_type: 'entry' }, { status: 201, statusText: 'Created' });
    http.expectOne('/api/v1/products/1/').flush({ ...PRODUCT, stock: '120.500', is_low: false });
    http.expectOne('/api/v1/products/1/movements/').flush(page([MOVEMENT]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('Entrée de 50,5 kg enregistrée.');
  });

  it('garde le même identifiant quand on réessaie après une coupure', async () => {
    fill('qty', '10');
    submit();
    const first = http.expectOne('/api/v1/products/1/movements/');
    const uuid = first.request.body.uuid;
    first.error(new ProgressEvent('error'));
    await fixture.whenStable();
    fixture.detectChanges();
    submit();
    const second = http.expectOne('/api/v1/products/1/movements/');
    expect(second.request.body.uuid).toBe(uuid);
    second.error(new ProgressEvent('error'));
  });
});
