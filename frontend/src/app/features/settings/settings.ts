import { Component, DestroyRef, computed, inject, signal } from '@angular/core';

import { firstMessage } from '../../core/api-errors';
import { DocumentSettings } from '../../core/documents.models';
import { DocumentService } from '../../core/documents.service';
import { compressLogo } from '../../core/image';
import { formatMoney } from '../../core/money';

const DEFAULT_ACCENT = '#1F7A4D';
const COLOR = /^#[0-9a-fA-F]{6}$/;
const PREFIX = /^[A-Z0-9]{1,10}$/;

type PreviewMode = 'invoice' | 'receipt';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class Settings {
  private readonly service = inject(DocumentService);
  protected readonly money = formatMoney;
  protected readonly today = new Date().toLocaleDateString('fr-FR');
  private readonly year = new Date().getFullYear();

  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);
  protected readonly settings = signal<DocumentSettings | null>(null);

  protected readonly business = signal('');
  protected readonly address = signal('');
  protected readonly phone = signal('');
  protected readonly email = signal('');
  protected readonly taxId = signal('');
  protected readonly registryId = signal('');
  protected readonly accent = signal(DEFAULT_ACCENT);
  protected readonly terms = signal('');
  protected readonly footer = signal('');
  protected readonly invoicePrefix = signal('FAC');
  protected readonly receiptPrefix = signal('REC');

  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly logoUrl = signal<string | null>(null);
  protected readonly logoBusy = signal(false);
  protected readonly logoError = signal<string | null>(null);
  private currentLogoUrl: string | null = null;

  protected readonly mode = signal<PreviewMode>('invoice');

  // Valeurs de l'exploitation : elles servent de repli quand un champ est laissé vide.
  protected readonly defaults = computed(
    () => this.settings()?.defaults ?? { name: '', address: '', phone: '', currency: 'GNF' },
  );
  protected readonly validAccent = computed(() =>
    COLOR.test(this.accent().trim()) ? this.accent().trim() : DEFAULT_ACCENT,
  );
  protected readonly previewName = computed(() => this.business().trim() || this.defaults().name);
  protected readonly previewAddress = computed(() => this.address().trim() || this.defaults().address);
  protected readonly previewPhone = computed(() => this.phone().trim() || this.defaults().phone);
  protected readonly docTitle = computed(() => (this.mode() === 'invoice' ? 'FACTURE' : 'REÇU'));
  protected readonly docNumber = computed(() => {
    const raw = (this.mode() === 'invoice' ? this.invoicePrefix() : this.receiptPrefix())
      .trim()
      .toUpperCase();
    const fallback = this.mode() === 'invoice' ? 'FAC' : 'REC';
    return `${PREFIX.test(raw) ? raw : fallback}-${this.year}-0001`;
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this.releaseLogo());
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.service.settings().subscribe({
      next: (settings) => {
        this.apply(settings);
        this.fill(settings);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(
          firstMessage(error, 'Impossible de charger les réglages. Réessayez dans un instant.'),
        );
        this.loading.set(false);
      },
    });
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLTextAreaElement).value;
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.save();
  }

  protected save(): void {
    if (this.saving()) return;
    const accent = this.accent().trim();
    if (!COLOR.test(accent)) {
      this.formError.set('Couleur invalide : utilisez le format #RRGGBB (ex. #1F7A4D).');
      return;
    }
    const invoicePrefix = this.invoicePrefix().trim().toUpperCase();
    const receiptPrefix = this.receiptPrefix().trim().toUpperCase();
    if (!PREFIX.test(invoicePrefix) || !PREFIX.test(receiptPrefix)) {
      this.formError.set('Préfixes de numéro : 1 à 10 lettres ou chiffres, sans espace ni tiret.');
      return;
    }
    this.saving.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.service
      .updateSettings({
        business_name: this.business().trim(),
        address: this.address().trim(),
        phone: this.phone().trim(),
        email: this.email().trim(),
        tax_id: this.taxId().trim(),
        registry_id: this.registryId().trim(),
        accent_color: accent.toUpperCase(),
        footer_text: this.footer().trim(),
        payment_terms: this.terms().trim(),
        invoice_prefix: invoicePrefix,
        receipt_prefix: receiptPrefix,
      })
      .subscribe({
        next: (settings) => {
          this.settings.set(settings);
          this.fill(settings);
          this.saving.set(false);
          this.notice.set('Réglages enregistrés. Ils s’appliquent aux prochains documents.');
        },
        error: (error: unknown) => {
          this.formError.set(
            firstMessage(error, 'L’enregistrement a échoué. Votre saisie est gardée : réessayez.'),
          );
          this.saving.set(false);
        },
      });
  }

  protected async chooseLogo(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // permet de rechoisir le même fichier
    if (!file || this.logoBusy()) return;
    this.logoBusy.set(true);
    this.logoError.set(null);
    this.notice.set(null);
    const blob = await compressLogo(file);
    this.service.uploadLogo(blob).subscribe({
      next: (settings) => {
        this.apply(settings);
        this.logoBusy.set(false);
        this.notice.set('Logo enregistré. Il apparaîtra sur les prochains documents.');
      },
      error: (error: unknown) => {
        this.logoError.set(
          firstMessage(error, 'L’envoi du logo a échoué. Vérifiez l’image (JPEG, PNG ou WebP) et réessayez.'),
        );
        this.logoBusy.set(false);
      },
    });
  }

  protected removeLogo(): void {
    if (this.logoBusy()) return;
    this.logoBusy.set(true);
    this.logoError.set(null);
    this.notice.set(null);
    this.service.deleteLogo().subscribe({
      next: (settings) => {
        this.apply(settings);
        this.logoBusy.set(false);
        this.notice.set('Logo retiré des prochains documents.');
      },
      error: (error: unknown) => {
        this.logoError.set(firstMessage(error, 'Le retrait du logo a échoué. Réessayez.'));
        this.logoBusy.set(false);
      },
    });
  }

  // Met à jour la version du serveur et recharge l'image du logo (protégée) si elle existe.
  private apply(settings: DocumentSettings): void {
    this.settings.set(settings);
    this.releaseLogo();
    this.logoUrl.set(null);
    if (!settings.has_logo) return;
    this.service.logoFile().subscribe({
      next: (blob) => {
        this.releaseLogo();
        this.currentLogoUrl = URL.createObjectURL(blob);
        this.logoUrl.set(this.currentLogoUrl);
      },
      error: () => this.logoUrl.set(null),
    });
  }

  private releaseLogo(): void {
    if (this.currentLogoUrl !== null) {
      URL.revokeObjectURL(this.currentLogoUrl);
      this.currentLogoUrl = null;
    }
  }

  private fill(settings: DocumentSettings): void {
    this.business.set(settings.business_name);
    this.address.set(settings.address);
    this.phone.set(settings.phone);
    this.email.set(settings.email);
    this.taxId.set(settings.tax_id);
    this.registryId.set(settings.registry_id);
    this.accent.set(settings.accent_color);
    this.terms.set(settings.payment_terms);
    this.footer.set(settings.footer_text);
    this.invoicePrefix.set(settings.invoice_prefix);
    this.receiptPrefix.set(settings.receipt_prefix);
  }
}
