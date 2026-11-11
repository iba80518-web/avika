import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Cycle } from '../../core/farming.models';
import { Cycles } from './cycles';

function cycle(id: number, name: string, status: Cycle['status']): Cycle {
  return {
    id, coop: 1, name, type: 'broiler', start_date: '2026-10-06', end_date: null,
    initial_count: 1000, supplier_name: '', unit_price: 9000, currency: 'GNF', target: '',
    planned_sale_date: null, status, current_count: 795, created_at: '2026-11-10T00:00:00Z',
  };
}

describe('Cycles', () => {
  let fixture: ComponentFixture<Cycles>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Cycles],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Cycles);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/cycles/').flush({
      count: 2, next: null, previous: null,
      results: [cycle(1, 'Bande A', 'active'), cycle(2, 'Bande Z', 'completed')],
    });
    http.expectOne('/api/v1/coops/').flush({
      count: 1, next: null, previous: null,
      results: [{ id: 1, farm: 1, name: 'Poulailler Nord', capacity: 1500, type: 'broiler', location: '', status: 'active', description: '' }],
    });
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('montre par défaut seulement les bandes en cours, avec le nom du poulailler', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Bande A');
    expect(text).toContain('Poulailler Nord');
    expect(text).not.toContain('Bande Z');
  });

  it('affiche toutes les bandes avec le filtre « Toutes »', () => {
    root.querySelectorAll<HTMLButtonElement>('.filters button')[1].click();
    fixture.detectChanges();
    expect(root.textContent).toContain('Bande Z');
  });
});
