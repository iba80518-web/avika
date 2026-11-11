import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormGroup } from '@angular/forms';
import { Router, provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { CycleForm } from './cycle-form';

const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
const COOP = { id: 2, farm: 1, name: 'Poulailler B', capacity: 800, type: 'broiler', location: '', status: 'active', description: '' };

describe('CycleForm', () => {
  let fixture: ComponentFixture<CycleForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CycleForm],
      providers: [
        provideRouter([{ path: 'bandes/:id', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { can: () => true } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(CycleForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    http.expectOne('/api/v1/coops/').flush(page([COOP]));
    http.expectOne('/api/v1/farms/').flush(page([{ id: 1, name: 'Site principal', location: '' }]));
    await fixture.whenStable();
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  const form = (): FormGroup => (fixture.componentInstance as unknown as { form: FormGroup }).form;
  const coopForm = (): FormGroup =>
    (fixture.componentInstance as unknown as { coopForm: FormGroup }).coopForm;
  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('ne contacte pas le serveur si le formulaire est incomplet', async () => {
    form().patchValue({ coop: null, name: '' });
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/cycles/');
    expect(root.textContent).toContain('Complétez les champs signalés.');
  });

  it('crée la bande puis ouvre son détail', async () => {
    form().patchValue({ coop: 2, name: 'Bande C', initial_count: 500, unit_price: 9000 });
    submit();
    const request = http.expectOne('/api/v1/cycles/');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.coop).toBe(2);
    expect(request.request.body.name).toBe('Bande C');
    expect(request.request.body.initial_count).toBe(500);
    expect(request.request.body.planned_sale_date).toBeNull();
    request.flush({ id: 7 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/bandes/7');
  });

  it('affiche le refus du serveur sous le bon champ', async () => {
    form().patchValue({ coop: 2, name: 'Bande B', initial_count: 500 });
    submit();
    http
      .expectOne('/api/v1/cycles/')
      .flush(
        { name: ['Ce poulailler a déjà un cycle portant ce nom.'] },
        { status: 400, statusText: 'Bad Request' },
      );
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('.field__error')?.textContent).toContain('déjà un cycle');
  });

  it('crée un poulailler sur place et le sélectionne', async () => {
    (Array.from(root.querySelectorAll<HTMLButtonElement>('.link'))[0]).click();
    fixture.detectChanges();
    coopForm().patchValue({ name: 'Nord', capacity: 600 });
    const create = Array.from(root.querySelectorAll<HTMLButtonElement>('.inline .btn')).find((item) =>
      item.textContent?.includes('Créer le poulailler'),
    ) as HTMLButtonElement;
    create.click();
    const request = http.expectOne('/api/v1/coops/');
    expect(request.request.body).toEqual({ farm: 1, name: 'Nord', capacity: 600, type: 'broiler' });
    request.flush({ ...COOP, id: 5, name: 'Nord', capacity: 600 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(form().value.coop).toBe(5);
  });
});
