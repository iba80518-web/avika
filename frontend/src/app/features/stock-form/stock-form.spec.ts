import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormGroup } from '@angular/forms';
import { Router, provideRouter } from '@angular/router';

import { StockForm } from './stock-form';

describe('StockForm', () => {
  let fixture: ComponentFixture<StockForm>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StockForm],
      providers: [
        provideRouter([{ path: 'stock/:id', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(StockForm);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  const form = (): FormGroup => (fixture.componentInstance as unknown as { form: FormGroup }).form;
  const submit = (): void => {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  };

  it('ne contacte pas le serveur si le nom est vide', async () => {
    submit();
    await fixture.whenStable();
    fixture.detectChanges();
    http.expectNone('/api/v1/products/');
    expect(root.textContent).toContain('Complétez les champs signalés.');
  });

  it('crée le produit puis ouvre sa fiche', async () => {
    form().patchValue({ name: 'Aliment croissance', product_type: 'feed', base_unit: 'kg', low_stock_threshold: 150 });
    submit();
    const request = http.expectOne('/api/v1/products/');
    expect(request.request.body).toEqual({
      name: 'Aliment croissance', product_type: 'feed', base_unit: 'kg', low_stock_threshold: 150,
    });
    request.flush({ id: 9 }, { status: 201, statusText: 'Created' });
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/stock/9');
  });

  it('affiche le refus du serveur sous le champ concerné', async () => {
    form().patchValue({ name: 'Aliment démarrage' });
    submit();
    http
      .expectOne('/api/v1/products/')
      .flush({ name: ['Un produit porte déjà ce nom.'] }, { status: 400, statusText: 'Bad Request' });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('.field__error')?.textContent).toContain('déjà ce nom');
  });
});
