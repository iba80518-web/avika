import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { OutboxStore } from '../../core/outbox.store';
import { SaleForm } from './sale-form';

const LAYER = { id: 5, name: 'Pondeuses A', type: 'layer', status: 'active', current_count: 900 };
const BROILER = { id: 6, name: 'Chair B', type: 'broiler', status: 'active', current_count: 400 };
const EMPTY = { count: 0, next: null, previous: null, results: [] };

describe('SaleForm — vente d\'œufs', () => {
  let http: HttpTestingController;

  function setup() {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([{ path: '**', children: [] }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(SaleForm);
    fixture.detectChanges();
    http
      .expectOne('/api/v1/cycles/')
      .flush({ count: 2, next: null, previous: null, results: [LAYER, BROILER] });
    http.match((r) => r.url.includes('customers')).forEach((r) => r.flush(EMPTY));
    fixture.detectChanges();
    return fixture;
  }

  function switchToEggs(fixture: ReturnType<typeof setup>) {
    const root = fixture.nativeElement as HTMLElement;
    const button = Array.from(root.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Œufs',
    ) as HTMLButtonElement;
    button.click();
    fixture.detectChanges();
    const select = root.querySelector('#cycle') as HTMLSelectElement;
    select.value = '5';
    select.dispatchEvent(new Event('change'));
    http
      .expectOne((r) => r.url === '/api/v1/egg-collections/summary/')
      .flush({ cycle: 5, stock: 290, days: [] });
    fixture.detectChanges();
    return root;
  }

  function type(root: HTMLElement, id: string, text: string) {
    const input = root.querySelector(`#${id}`) as HTMLInputElement;
    input.value = text;
    input.dispatchEvent(new Event('input'));
  }

  afterEach(() => http.verify());

  it('ne propose que les bandes de pondeuses et affiche le stock', () => {
    const fixture = setup();
    const root = switchToEggs(fixture);
    const options = Array.from(root.querySelectorAll('#cycle option')).map((o) => o.textContent);
    expect(options.join('|')).toContain('Pondeuses A');
    expect(options.join('|')).not.toContain('Chair B');
    expect(root.textContent).toContain('290');
  });

  it('envoie une vente d\'œufs au plateau, tarif détail, avec le bon total', () => {
    const fixture = setup();
    const root = switchToEggs(fixture);
    type(root, 'qty', '5');
    type(root, 'price', '3000');
    fixture.detectChanges();
    expect(root.textContent).toContain('150');

    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const request = http.expectOne('/api/v1/sales/');
    const body = request.request.body;
    expect(body.product).toBe('eggs');
    expect(body.egg_unit).toBe('tray');
    expect(body.price_tier).toBe('retail');
    expect(body.sale_type).toBe('count');
    expect(body.cycle).toBe(5);
    expect(body.quantity).toBe(5);
    expect(body.unit_price).toBe(3000);
    expect(body.paid_amount).toBe(15000);
    expect(body.weight_kg).toBeUndefined();
    request.flush({ id: 9 });
  });

  it('refuse une vente supérieure au stock sans appeler le serveur', () => {
    const fixture = setup();
    const root = switchToEggs(fixture);
    type(root, 'qty', '20'); // 20 plateaux = 600 œufs, pour 290 en stock
    type(root, 'price', '3000');
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(root.textContent).toContain('Il ne reste que 290 œufs');
  });
  it('garde la vente sur le téléphone quand le réseau manque', async () => {
    const fixture = setup();
    TestBed.inject(OutboxStore).forceMemory();
    const root = switchToEggs(fixture);
    type(root, 'qty', '5');
    type(root, 'price', '3000');
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectOne('/api/v1/sales/').error(new ProgressEvent('error'));
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
    expect(root.textContent).toContain('gardée sur ce téléphone');
  });
});
