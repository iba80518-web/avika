import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth.service';
import { PhotoCapture } from './photo-capture';

describe('PhotoCapture', () => {
  let http: HttpTestingController;

  function setup(allowed: boolean) {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { can: () => allowed } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(PhotoCapture);
    fixture.componentRef.setInput('cycle', 5);
    fixture.componentRef.setInput('kind', 'eggs');
    fixture.componentRef.setInput('date', '2026-10-03');
    fixture.componentRef.setInput('eggCollection', 7);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => http.verify());

  it('reste caché pour un rôle sans le droit d\'envoyer des photos', () => {
    const fixture = setup(false);
    expect(fixture.nativeElement.querySelector('input[type="file"]')).toBeNull();
  });

  it('ouvre l\'appareil photo arrière sur téléphone', () => {
    const fixture = setup(true);
    const input = fixture.nativeElement.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.getAttribute('accept')).toBe('image/*');
    expect(input.getAttribute('capture')).toBe('environment');
  });

  it('envoie la photo choisie avec son type, sa date et son ramassage', async () => {
    const fixture = setup(true);
    const root = fixture.nativeElement as HTMLElement;
    const input = root.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['abc'], 'p.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    fixture.detectChanges();

    const send = Array.from(root.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Envoyer'),
    ) as HTMLButtonElement;
    send.click();
    const request = http.expectOne('/api/v1/photos/');
    const form = request.request.body as FormData;
    expect(form.get('kind')).toBe('eggs');
    expect(form.get('cycle')).toBe('5');
    expect(form.get('taken_date')).toBe('2026-10-03');
    expect(form.get('egg_collection')).toBe('7');
    request.flush({ id: 1 });
    fixture.detectChanges();
    expect(root.textContent).toContain('Photo envoyée');
  });
});
