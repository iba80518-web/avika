import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { PhotoService } from './photo.service';

describe('PhotoService', () => {
  let service: PhotoService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PhotoService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('envoie la photo en formulaire avec son type, sa date et son identifiant', () => {
    service
      .upload({
        cycle: 3, kind: 'eggs', taken_date: '2026-10-03', uuid: 'u-1',
        image: new Blob(['x'], { type: 'image/jpeg' }), egg_collection: 7,
      })
      .subscribe();
    const req = http.expectOne('/api/v1/photos/');
    const form = req.request.body as FormData;
    expect(form instanceof FormData).toBe(true);
    expect(form.get('cycle')).toBe('3');
    expect(form.get('kind')).toBe('eggs');
    expect(form.get('taken_date')).toBe('2026-10-03');
    expect(form.get('uuid')).toBe('u-1');
    expect(form.get('egg_collection')).toBe('7');
    expect(form.get('flock_event')).toBeNull();
    expect(form.get('image') instanceof Blob).toBe(true);
    req.flush({});
  });

  it('filtre la liste par bande et par type', () => {
    service.list({ cycle: 3, kind: 'mortality' }).subscribe();
    const req = http.expectOne((r) => r.url === '/api/v1/photos/');
    expect(req.request.params.get('cycle')).toBe('3');
    expect(req.request.params.get('kind')).toBe('mortality');
    req.flush({ count: 0, next: null, previous: null, results: [] });
  });
});
