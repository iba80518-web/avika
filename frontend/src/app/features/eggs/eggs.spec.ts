import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Eggs } from './eggs';

const LAYER = { id: 5, name: 'Pondeuses A', type: 'layer', status: 'active' };
const BROILER = { id: 6, name: 'Chair B', type: 'broiler', status: 'active' };
const SUMMARY = {
  cycle: 5,
  stock: 435,
  days: [{ date: '2026-10-03', collected: 450, broken: 15, hens: 1000, rate: 45 }],
};

describe('Eggs', () => {
  let http: HttpTestingController;

  function setup() {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(Eggs);
    fixture.detectChanges();
    http
      .expectOne('/api/v1/cycles/')
      .flush({ count: 2, next: null, previous: null, results: [LAYER, BROILER] });
    const summary = http.expectOne((r) => r.url === '/api/v1/egg-collections/summary/');
    expect(summary.request.params.get('cycle')).toBe('5');
    summary.flush(SUMMARY);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('choisit la bande de pondeuses et affiche le stock et le taux de ponte', () => {
    const root = (setup().nativeElement as HTMLElement).textContent ?? '';
    expect(root).toContain('435');
    expect(root).toContain('45 %');
    expect(root).not.toContain('Chair B');
  });

  it('enregistre un ramassage avec la bonne bande, les œufs ramassés et cassés', () => {
    const fixture = setup();
    const root = fixture.nativeElement as HTMLElement;
    const type = (id: string, text: string) => {
      const input = root.querySelector(`#${id}`) as HTMLInputElement;
      input.value = text;
      input.dispatchEvent(new Event('input'));
    };
    type('collected', '300');
    type('broken', '10');
    fixture.detectChanges();
    expect(root.textContent).toContain('290');

    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const create = http.expectOne('/api/v1/egg-collections/');
    expect(create.request.method).toBe('POST');
    expect(create.request.body.cycle).toBe(5);
    expect(create.request.body.collected).toBe(300);
    expect(create.request.body.broken).toBe(10);
    expect(typeof create.request.body.uuid).toBe('string');
    create.flush({});

    http.expectOne((r) => r.url === '/api/v1/egg-collections/summary/').flush(SUMMARY);
    fixture.detectChanges();
    expect(root.textContent).toContain('Ramassage enregistré');
  });

  it('refuse plus d’œufs cassés que d’œufs ramassés sans appeler le serveur', () => {
    const fixture = setup();
    const root = fixture.nativeElement as HTMLElement;
    const type = (id: string, text: string) => {
      const input = root.querySelector(`#${id}`) as HTMLInputElement;
      input.value = text;
      input.dispatchEvent(new Event('input'));
    };
    type('collected', '10');
    type('broken', '11');
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(root.textContent).toContain('plus d’œufs cassés');
  });
});
