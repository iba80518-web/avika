import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { formatMoney } from '../../core/money';
import { Expenses } from './expenses';

const expense = (id: number, category: string, amount: number, description: string, cycle: number | null) => ({
  id, uuid: 'e' + id, amount, expense_date: '2026-11-05', category, description, supplier: null, cycle,
  created_by: 3, created_at: '2026-11-10T00:00:00Z',
});
const CYCLE = {
  id: 1, coop: 1, name: 'Bande A', type: 'broiler', start_date: '2026-10-01', end_date: null,
  initial_count: 1000, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
  planned_sale_date: null, status: 'active', current_count: 700, created_at: '2026-11-10T00:00:00Z',
};
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('Expenses', () => {
  let fixture: ComponentFixture<Expenses>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Expenses],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Expenses);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/expenses/').flush(
      page([
        expense(1, 'transport', 15000, '', 1),
        expense(2, 'labor', 100000, 'Salaire gardien', null),
      ]),
    );
    http.expectOne('/api/v1/cycles/').flush(page([CYCLE]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('liste les dépenses avec leur bande ou « Dépense générale »', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Salaire gardien');
    expect(text).toContain('Bande A');
    expect(text).toContain('Dépense générale');
    expect(text).toContain(formatMoney(15000));
  });

  it('totalise et classe les catégories par montant', () => {
    expect(root.textContent).toContain(formatMoney(115000));
    const first = root.querySelector('.bars li')?.textContent ?? '';
    expect(first).toContain('Main-d’œuvre');
    expect(root.querySelectorAll('.bars li').length).toBe(2);
  });
});
