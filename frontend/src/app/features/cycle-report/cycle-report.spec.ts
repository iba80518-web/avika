import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { CycleReport } from './cycle-report';

const URL_TEXT = '/api/v1/reports/7/whatsapp/';
const URL_PDF = '/api/v1/reports/7/pdf/';
const REPORT = { cycle: 7, text: 'Bilan Bande B\nEffectif : 430', whatsapp_url: 'https://wa.me/?text=Bilan' };
const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('CycleReport', () => {
  let fixture: ComponentFixture<CycleReport>;
  let root: HTMLElement;
  let http: HttpTestingController;
  const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };

  const button = (label: string): HTMLButtonElement =>
    Array.from(root.querySelectorAll('button')).find((item) =>
      item.textContent?.trim().startsWith(label),
    ) as HTMLButtonElement;

  async function prepared(report = REPORT): Promise<void> {
    button('Préparer le rapport').click();
    http.expectOne(URL_TEXT).flush(report);
    await tick();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    Object.assign(URL, { createObjectURL: () => 'blob:test', revokeObjectURL: () => undefined });
    await TestBed.configureTestingModule({
      imports: [CycleReport],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(CycleReport);
    fixture.componentRef.setInput('cycleId', 7);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  afterEach(() => {
    http.verify();
    vi.restoreAllMocks();
    Object.assign(URL, { createObjectURL: original.create, revokeObjectURL: original.revoke });
  });

  it('ne charge rien tant qu’on ne le demande pas, puis affiche le bilan', async () => {
    http.expectNone(URL_TEXT);
    await prepared();
    expect(root.querySelector('.report')?.textContent).toContain('Effectif : 430');
  });

  it('ouvre WhatsApp avec le lien du serveur', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    await prepared();
    button('Partager sur WhatsApp').click();
    expect(open).toHaveBeenCalledWith('https://wa.me/?text=Bilan', '_blank', 'noopener');
  });

  it('refuse d’ouvrir un lien qui n’est pas WhatsApp', async () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    await prepared({ ...REPORT, whatsapp_url: 'https://pirate.example/x' });
    button('Partager sur WhatsApp').click();
    fixture.detectChanges();
    expect(open).not.toHaveBeenCalled();
    expect(root.textContent).toContain('Lien de partage invalide');
  });

  it('copie le texte du bilan', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    await prepared();
    button('Copier le texte').click();
    await tick();
    fixture.detectChanges();
    expect(writeText).toHaveBeenCalledWith(REPORT.text);
    expect(root.textContent).toContain('Texte copié');
  });

  it('télécharge le PDF, et montre l’erreur du serveur si le bilan échoue', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    await prepared();
    button('Télécharger le PDF').click();
    http.expectOne(URL_PDF).flush(new Blob(['%PDF'], { type: 'application/pdf' }));
    await tick();
    expect(click).toHaveBeenCalledTimes(1);

    button('Actualiser').click();
    http.expectOne(URL_TEXT).flush({ detail: 'Indisponible.' }, { status: 500, statusText: 'x' });
    await tick();
    fixture.detectChanges();
    expect(root.querySelector('.form-error')).not.toBeNull();
  });
});
