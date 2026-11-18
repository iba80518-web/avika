import { Component, inject, input, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { downloadBlob } from '../../core/download';
import { ReportService } from '../../core/report.service';

// On n'ouvre que de vrais liens WhatsApp, même si la réponse du serveur disait autre chose.
const WHATSAPP_PREFIXES = ['https://wa.me/', 'https://api.whatsapp.com/'];
const OFFLINE = 'Pas de connexion : le rapport se prépare en ligne. Réessayez quand le réseau revient.';

@Component({
  selector: 'app-cycle-report',
  templateUrl: './cycle-report.html',
  styleUrl: './cycle-report.scss',
})
export class CycleReport {
  readonly cycleId = input.required<number>();
  private readonly service = inject(ReportService);

  protected readonly text = signal<string | null>(null);
  protected readonly whatsappUrl = signal<string | null>(null);
  protected readonly busy = signal<'text' | 'pdf' | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  private offline(): boolean {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.error.set(OFFLINE);
      return true;
    }
    return false;
  }

  protected prepare(): void {
    if (this.busy() !== null || this.offline()) return;
    this.busy.set('text');
    this.error.set(null);
    this.notice.set(null);
    this.service.whatsapp(this.cycleId()).subscribe({
      next: (report) => {
        this.text.set(report.text);
        this.whatsappUrl.set(report.whatsapp_url);
        this.busy.set(null);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Le rapport n’a pas pu être préparé. Réessayez dans un instant.'));
        this.busy.set(null);
      },
    });
  }

  protected share(): void {
    const url = this.whatsappUrl();
    if (!url || !WHATSAPP_PREFIXES.some((prefix) => url.startsWith(prefix))) {
      this.error.set('Lien de partage invalide : copiez le texte et collez-le dans WhatsApp.');
      return;
    }
    this.error.set(null);
    window.open(url, '_blank', 'noopener');
  }

  protected async copy(): Promise<void> {
    const text = this.text();
    if (text === null) return;
    try {
      await navigator.clipboard.writeText(text);
      this.error.set(null);
      this.notice.set('Texte copié : collez-le où vous voulez.');
    } catch {
      this.error.set('Copie impossible : sélectionnez le texte à la main.');
    }
  }

  protected async downloadPdf(): Promise<void> {
    if (this.busy() !== null || this.offline()) return;
    this.busy.set('pdf');
    this.error.set(null);
    this.notice.set(null);
    try {
      const blob = await firstValueFrom(this.service.pdf(this.cycleId()));
      downloadBlob(blob, `rapport-bande-${this.cycleId()}.pdf`);
    } catch (error: unknown) {
      this.error.set(firstMessage(error, 'Le PDF n’a pas pu être créé. Réessayez dans un instant.'));
    } finally {
      this.busy.set(null);
    }
  }
}
