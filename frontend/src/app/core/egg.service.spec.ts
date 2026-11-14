import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { EggService } from './egg.service';

describe('EggService', () => {
  let service: EggService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(EggService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('liste les ramassages d\'une bande', () => {
    service.list(3).subscribe();
    const req = http.expectOne((r) => r.url === '/api/v1/egg-collections/');
    expect(req.request.params.get('cycle')).toBe('3');
    req.flush({ count: 0, next: null, previous: null, results: [] });
  });

  it('lit le résumé avec le stock et le taux de ponte', () => {
    let stock = -1;
    service.summary(3).subscribe((summary) => (stock = summary.stock));
    const req = http.expectOne((r) => r.url === '/api/v1/egg-collections/summary/');
    expect(req.request.params.get('cycle')).toBe('3');
    req.flush({ cycle: 3, stock: 435, days: [] });
    expect(stock).toBe(435);
  });

  it('enregistre un ramassage avec son identifiant', () => {
    const body = {
      cycle: 3, collected_date: '2026-10-03', collected: 300, broken: 10, note: '', uuid: 'u-1',
    };
    service.create(body).subscribe();
    const req = http.expectOne('/api/v1/egg-collections/');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(body);
    req.flush({});
  });

  it('corrige un ramassage', () => {
    service.update(9, { collected: 320, broken: 20, note: 'Recompté' }).subscribe();
    const req = http.expectOne('/api/v1/egg-collections/9/');
    expect(req.request.method).toBe('PATCH');
    req.flush({});
  });
});
