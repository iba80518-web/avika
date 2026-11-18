import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Settings } from './settings';

const URL_SETTINGS = '/api/v1/document-settings/';
const SETTINGS = {
  business_name: '', address: '', phone: '', email: '', tax_id: '', registry_id: '',
  accent_color: '#1F7A4D', footer_text: '', payment_terms: '',
  invoice_prefix: 'FAC', receipt_prefix: 'REC', has_logo: false, logo_url: null,
  defaults: { name: 'Ferme Test', address: 'Kaloum', phone: '620000000', currency: 'GNF' },
};

describe('Settings', () => {
  let fixture: ComponentFixture<Settings>;
  let root: HTMLElement;
  let http: HttpTestingController;

  async function settle(): Promise<void> {
    await fixture.whenStable();
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();
  }

  async function open(failure = false): Promise<void> {
    await TestBed.configureTestingModule({
      imports: [Settings],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Settings);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    const request = http.expectOne(URL_SETTINGS);
    if (failure) request.error(new ProgressEvent('error'));
    else request.flush(SETTINGS);
    await settle();
  }

  function fill(id: string, value: string): void {
    const input = root.querySelector<HTMLInputElement>('#' + id) as HTMLInputElement;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
  }

  function submit(): void {
    (root.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
  }

  afterEach(() => http.verify());

  it('reprend les valeurs de l’exploitation dans l’aperçu quand les champs sont vides', async () => {
    await open();
    expect(root.querySelector('.sheet')?.textContent).toContain('Ferme Test');
    expect(root.querySelector('.sheet')?.textContent).toContain('Kaloum');
    expect(root.querySelector('.sheet')?.textContent).toContain('FAC-');
    expect(root.querySelector<HTMLInputElement>('#business')?.placeholder).toBe('Ferme Test');
  });

  it('met l’aperçu à jour à chaque frappe', async () => {
    await open();
    fill('business', 'Ferme du Soleil');
    fill('invoice-prefix', 'fa2');
    fill('tax-id', 'NIF-9');
    const sheet = root.querySelector('.sheet')?.textContent ?? '';
    expect(sheet).toContain('Ferme du Soleil');
    expect(sheet).toContain('FA2-');
    expect(sheet).toContain('NIF : NIF-9');
  });

  it('refuse une couleur invalide sans appeler le serveur', async () => {
    await open();
    fill('accent-text', 'vert');
    submit();
    fixture.detectChanges();
    expect(root.textContent).toContain('Couleur invalide');
    http.expectNone(URL_SETTINGS);
  });

  it('enregistre les réglages saisis', async () => {
    await open();
    fill('business', 'Ferme du Soleil');
    fill('footer', 'Merci !');
    submit();
    const request = http.expectOne(URL_SETTINGS);
    expect(request.request.method).toBe('PATCH');
    expect(request.request.body.business_name).toBe('Ferme du Soleil');
    expect(request.request.body.footer_text).toBe('Merci !');
    expect(request.request.body.accent_color).toBe('#1F7A4D');
    expect(request.request.body.invoice_prefix).toBe('FAC');
    request.flush({ ...SETTINGS, business_name: 'Ferme du Soleil', footer_text: 'Merci !' });
    await settle();
    expect(root.textContent).toContain('Réglages enregistrés');
  });

  it('montre l’erreur de chargement et permet de réessayer', async () => {
    await open(true);
    expect(root.textContent).toContain('Pas de connexion');
    (root.querySelector('.state button') as HTMLButtonElement).click();
    http.expectOne(URL_SETTINGS).flush(SETTINGS);
    await settle();
    expect(root.textContent).toContain('Vos coordonnées');
  });

  it('envoie le logo choisi puis l’affiche', async () => {
    const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
    Object.assign(URL, { createObjectURL: () => 'blob:test', revokeObjectURL: () => undefined });
    try {
      await open();
      const input = root.querySelector<HTMLInputElement>('#logo') as HTMLInputElement;
      Object.defineProperty(input, 'files', {
        value: [new File(['x'], 'logo.png', { type: 'image/png' })],
        configurable: true,
      });
      input.dispatchEvent(new Event('change'));
      await settle();
      const upload = http.expectOne(`${URL_SETTINGS}logo/`);
      expect(upload.request.method).toBe('POST');
      upload.flush({ ...SETTINGS, has_logo: true, logo_url: `${URL_SETTINGS}logo/file/` });
      await settle();
      http.expectOne(`${URL_SETTINGS}logo/file/`).flush(new Blob(['x'], { type: 'image/png' }));
      await settle();
      expect(root.querySelector('img.logo')).not.toBeNull();
      expect(root.textContent).toContain('Logo enregistré');
    } finally {
      Object.assign(URL, { createObjectURL: original.create, revokeObjectURL: original.revoke });
    }
  });
});
