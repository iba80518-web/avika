import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';
import { SubmitResult } from './outbox.service';
import { OutboxService } from './outbox.service';
import { OutboxStore } from './outbox.store';

const URL = '/api/v1/photos/';
const FIELDS = {
  cycle: '5',
  kind: 'eggs',
  taken_date: '2026-10-03',
  uuid: 'p-1',
  egg_collection_uuid: 'c-1',
};

describe('OutboxService — photos', () => {
  let service: OutboxService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { activeOrganizationId: () => 1 } },
      ],
    });
    TestBed.inject(OutboxStore).forceMemory();
    service = TestBed.inject(OutboxService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('envoie la photo en formulaire avec tous ses champs quand le réseau est là', () => {
    let outcome: SubmitResult<unknown> | undefined;
    service.submitPhoto('Photo', URL, FIELDS, new Blob(['x']), 'p-1').subscribe((r) => (outcome = r));
    const request = http.expectOne(URL);
    const form = request.request.body as FormData;
    expect(form.get('egg_collection_uuid')).toBe('c-1');
    expect(form.get('uuid')).toBe('p-1');
    expect(form.get('image') instanceof Blob).toBe(true);
    request.flush({ id: 1 });
    expect(outcome).toEqual({ queued: false, result: { id: 1 } });
  });

  it('garde la photo avec son fichier sans réseau, puis la renvoie à l\'identique', async () => {
    service.submitPhoto('Photo', URL, FIELDS, new Blob(['abc']), 'p-1').subscribe();
    http.expectOne(URL).error(new ProgressEvent('error'));
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    expect(service.pending().length).toBe(1);
    expect(service.pending()[0].uuid).toBe('p-1');
    expect(service.pending()[0].file instanceof Blob).toBe(true);

    const flushing = service.flush();
    const retry = http.expectOne(URL);
    const form = retry.request.body as FormData;
    expect(form.get('uuid')).toBe('p-1');
    expect(form.get('egg_collection_uuid')).toBe('c-1');
    expect(form.get('image') instanceof Blob).toBe(true);
    retry.flush({ id: 1 });
    await flushing;
    expect(service.pending().length).toBe(0);
  });

  it('ne garde pas deux fois la même photo', async () => {
    for (let i = 0; i < 2; i++) {
      service.submitPhoto('Photo', URL, FIELDS, new Blob(['abc']), 'p-1').subscribe();
      http.expectOne(URL).error(new ProgressEvent('error'));
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    }
    expect(service.pending().length).toBe(1);
  });
});
