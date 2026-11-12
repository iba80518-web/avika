import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { localToday } from '../../core/dates';
import { Health } from './health';

const task = (id: number, name: string, due: string, product: number | null, productName: string | null) => ({
  id, uuid: 't' + id, cycle: 1, cycle_name: 'Bande A', name, kind: 'vaccine', due_date: due, status: 'planned',
  done_date: null, product, product_name: productName, quantity: null, note: '', created_by: 3,
  created_at: '2026-11-10T00:00:00Z',
});
const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });

describe('Health', () => {
  let fixture: ComponentFixture<Health>;
  let root: HTMLElement;
  let http: HttpTestingController;
  const late = task(1, 'Gumboro', '2020-01-01', null, null);
  const now = task(2, 'Newcastle', localToday(), 3, 'Vaccin Newcastle');

  function answerLoad(): void {
    http.expectOne('/api/v1/health-tasks/?status=planned').flush(page([late, now]));
    http.expectOne('/api/v1/health-tasks/reminders/').flush({ overdue: [late], today: [now], tomorrow: [] });
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Health],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Health);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    answerLoad();
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function inRow(name: string, label: string): void {
    const row = Array.from(root.querySelectorAll('article.row')).find((item) => item.textContent?.includes(name));
    const button = Array.from(row?.querySelectorAll<HTMLButtonElement>('button') ?? []).find((item) =>
      item.textContent?.includes(label),
    );
    (button as HTMLButtonElement).click();
    fixture.detectChanges();
  }

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('affiche les rappels et l’état de chaque tâche', () => {
    const text = root.textContent ?? '';
    expect(text).toContain('Gumboro');
    expect(text).toContain('En retard');
    expect(text).toContain('Aujourd’hui');
    expect(root.querySelector('.kpi__value.is-alert')?.textContent).toContain('1');
  });

  it('réalise une tâche en retirant la quantité du stock', async () => {
    inRow('Newcastle', 'Réaliser');
    fill('doneQty', '2,5');
    const box = root.querySelector<HTMLInputElement>('#useStock') as HTMLInputElement;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    submit();
    const request = http.expectOne('/api/v1/health-tasks/2/complete/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ done_date: localToday(), use_stock: true, quantity: 2.5 });
    request.flush({ ...now, status: 'done', done_date: localToday() });
    answerLoad();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('« Newcastle » est marquée comme réalisée.');
  });

  it('refuse de retirer du stock sans quantité, sans contacter le serveur', async () => {
    inRow('Newcastle', 'Réaliser');
    const box = root.querySelector<HTMLInputElement>('#useStock') as HTMLInputElement;
    box.checked = true;
    box.dispatchEvent(new Event('change'));
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/health-tasks/2/complete/');
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('quantité utilisée');
  });

  it('annule une tâche après confirmation', async () => {
    inRow('Gumboro', 'Annuler');
    inRow('Gumboro', 'Oui, annuler');
    const request = http.expectOne('/api/v1/health-tasks/1/cancel/');
    expect(request.request.method).toBe('POST');
    request.flush({ ...late, status: 'cancelled' });
    answerLoad();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).toContain('« Gumboro » est annulée.');
  });
});
