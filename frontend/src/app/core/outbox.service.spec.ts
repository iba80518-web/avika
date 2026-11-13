import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { AuthService } from './auth.service';
import { OutboxService } from './outbox.service';
import { OutboxStore } from './outbox.store';

const URL = '/api/v1/cycles/2/mortality/';
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('OutboxService', () => {
  let service: OutboxService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { activeOrganizationId: () => 7 } },
      ],
    });
    TestBed.inject(OutboxStore).forceMemory();
    service = TestBed.inject(OutboxService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  async function queueTwoOffline(): Promise<void> {
    service.online.set(false);
    await firstValueFrom(service.submit('Mortalité', URL, { n: 1 }, 'u1'));
    await firstValueFrom(service.submit('Mortalité', URL, { n: 2 }, 'u2'));
    service.online.set(true);
  }

  it('envoie tout de suite quand le réseau est là', async () => {
    const result = firstValueFrom(service.submit('Mortalité', URL, { n: 1 }, 'u1'));
    http.expectOne(URL).flush({ ok: true }, { status: 201, statusText: 'Created' });
    expect(await result).toEqual({ queued: false, result: { ok: true } });
    expect(service.pending().length).toBe(0);
  });

  it('garde la saisie quand le réseau coupe en cours d’envoi', async () => {
    const result = firstValueFrom(service.submit('Mortalité', URL, { n: 1 }, 'u1'));
    http.expectOne(URL).error(new ProgressEvent('error'));
    expect(await result).toEqual({ queued: true });
    expect(service.pending().length).toBe(1);
  });

  it('garde la saisie sans contacter le serveur quand on est hors connexion, sans doublon', async () => {
    service.online.set(false);
    await firstValueFrom(service.submit('Mortalité', URL, { n: 1 }, 'u1'));
    await firstValueFrom(service.submit('Mortalité', URL, { n: 1 }, 'u1'));
    http.expectNone(URL);
    expect(service.pending().length).toBe(1);
  });

  it('renvoie les saisies dans l’ordre puis vide la boîte', async () => {
    await queueTwoOffline();
    const done = service.flush();
    const first = http.expectOne(URL);
    expect(first.request.body.n).toBe(1);
    first.flush({}, { status: 201, statusText: 'Created' });
    await tick();
    const second = http.expectOne(URL);
    expect(second.request.body.n).toBe(2);
    second.flush({}, { status: 200, statusText: 'OK' });
    await done;
    expect(service.pending().length).toBe(0);
  });

  it('s’arrête quand le réseau lâche et garde tout pour plus tard', async () => {
    await queueTwoOffline();
    const done = service.flush();
    http.expectOne(URL).error(new ProgressEvent('error'));
    await done;
    http.expectNone(URL);
    expect(service.pending().length).toBe(2);
  });

  it('marque une saisie refusée par le serveur sans bloquer les suivantes', async () => {
    await queueTwoOffline();
    const done = service.flush();
    http.expectOne(URL).flush({ detail: 'Ce cycle est terminé.' }, { status: 400, statusText: 'Bad Request' });
    await tick();
    http.expectOne(URL).flush({}, { status: 201, statusText: 'Created' });
    await done;
    expect(service.rejected().length).toBe(1);
    expect(service.pending().length).toBe(0);
    await service.dismiss(service.rejected()[0].id);
    expect(service.rejected().length).toBe(0);
  });
});
