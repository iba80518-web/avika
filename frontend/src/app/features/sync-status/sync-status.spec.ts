import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { OutboxService } from '../../core/outbox.service';
import { OutboxStore } from '../../core/outbox.store';
import { SyncStatus } from './sync-status';

const URL = '/api/v1/cycles/2/events/';
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('SyncStatus', () => {
  let service: OutboxService;
  let http: HttpTestingController;
  let fixture: ComponentFixture<SyncStatus>;
  let root: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SyncStatus],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { activeOrganizationId: () => 7 } },
      ],
    }).compileComponents();
    TestBed.inject(OutboxStore).forceMemory();
    service = TestBed.inject(OutboxService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function show(): void {
    fixture = TestBed.createComponent(SyncStatus);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  }

  it('reste invisible quand tout est envoyé et que le réseau est là', () => {
    show();
    expect(root.querySelector('.sync__toggle')).toBeNull();
  });

  it('signale la perte de réseau et le nombre de saisies en attente', async () => {
    service.online.set(false);
    await firstValueFrom(service.submit('Mortalité · Bande A', URL, { n: 1 }, 'u1'));
    show();
    const text = root.textContent ?? '';
    expect(text).toContain('Hors connexion');
    expect(text).toContain('1 saisie en attente');
  });

  it('montre une saisie refusée avec la possibilité de la supprimer', async () => {
    service.online.set(false);
    await firstValueFrom(service.submit('Mortalité · Bande A', URL, { n: 1 }, 'u1'));
    service.online.set(true);
    show();
    await tick();
    http.expectOne(URL).flush({ detail: 'Ce cycle est terminé.' }, { status: 400, statusText: 'Bad Request' });
    await tick();
    fixture.detectChanges();
    expect(root.textContent).toContain('refusée');
    (root.querySelector('.sync__toggle') as HTMLButtonElement).click();
    fixture.detectChanges();
    const remove = Array.from(root.querySelectorAll<HTMLButtonElement>('.sync__panel button')).find((item) =>
      item.textContent?.includes('Supprimer'),
    );
    (remove as HTMLButtonElement).click();
    await tick();
    fixture.detectChanges();
    expect(root.querySelector('.sync__toggle')).toBeNull();
  });
});
