import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Stock } from './stock';

const product = (id: number, name: string, type: string, stock: string, value: number, low: boolean) => ({
  id, name, product_type: type, base_unit: type === 'feed' ? 'kg' : 'dose', low_stock_threshold: '100.000',
  is_active: true, stock, stock_value: value, is_low: low, created_at: '2026-11-10T00:00:00Z',
});

describe('Stock', () => {
  let fixture: ComponentFixture<Stock>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Stock],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Stock);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/products/').flush({
      count: 2, next: null, previous: null,
      results: [
        product(1, 'Aliment démarrage', 'feed', '70.000', 140000, true),
        product(2, 'Vaccin Newcastle', 'vaccine', '1500.000', 300000, false),
      ],
    });
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('groupe les produits par type et signale le stock bas', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Aliments');
    expect(text).toContain('Vaccins');
    expect(text).toContain('Aliment démarrage');
    expect(root.querySelectorAll('.pill--danger').length).toBe(1);
  });

  it('résume la valeur du stock et le nombre de produits sous le seuil', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('440 k');
    expect(root.querySelector('.kpi__value.is-alert')?.textContent).toContain('1');
  });
});
