import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, firstValueFrom, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday, shortDate } from '../../core/dates';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { PaymentMethod, Sale, SalePayment } from '../../core/finance.models';
import { FinanceService } from '../../core/finance.service';
import { DocumentKind } from '../../core/documents.models';
import { DocumentService } from '../../core/documents.service';
import { downloadBlob } from '../../core/download';
import { formatMoney } from '../../core/money';
import { parseNumber } from '../../core/numbers';
import { newUuid } from '../../core/uuid';
import { soldLabel, tierLabel } from '../../core/sale-labels';

const EMPTY_CYCLES: Page<Cycle> = { count: 0, next: null, previous: null, results: [] };

const METHOD_LABELS: Record<string, string> = {
  cash: 'Espèces',
  mobile_money: 'Mobile money',
  bank_transfer: 'Virement',
  other: 'Autre',
};

@Component({
  selector: 'app-sale-detail',
  imports: [RouterLink],
  templateUrl: './sale-detail.html',
  styleUrl: './sale-detail.scss',
})
export class SaleDetail {
  protected readonly sold = soldLabel;
  protected readonly tier = tierLabel;
  private readonly finance = inject(FinanceService);
  private readonly farming = inject(FarmingService);
  private readonly documents = inject(DocumentService);
  private readonly saleId = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));

  protected readonly methods: { value: PaymentMethod; label: string }[] = [
    { value: 'cash', label: 'Espèces' },
    { value: 'mobile_money', label: 'Mobile money' },
    { value: 'bank_transfer', label: 'Virement' },
    { value: 'other', label: 'Autre' },
  ];
  protected readonly today = localToday();
  protected readonly money = formatMoney;
  protected readonly shortDate = shortDate;

  protected readonly sale = signal<Sale | null>(null);
  protected readonly payments = signal<SalePayment[]>([]);
  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly amount = signal('');
  protected readonly payDate = signal(localToday());
  protected readonly method = signal<PaymentMethod>('cash');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly confirming = signal(false);
  protected readonly reason = signal('');
  protected readonly cancelling = signal(false);
  protected readonly cancelError = signal<string | null>(null);

  // Documents : nom saisi pour une vente de passage, document en cours de création, erreur.
  protected readonly guestName = signal('');
  protected readonly docBusy = signal<string | null>(null);
  protected readonly docError = signal<string | null>(null);
  protected readonly canShare = typeof navigator !== 'undefined' && typeof navigator.canShare === 'function';

  // Gardé tant que le paiement n'a pas réussi : un nouvel essai ne peut pas l'encaisser deux fois.
  private pendingUuid = newUuid();

  protected readonly cycle = computed(() => {
    const sale = this.sale();
    if (!sale) return null;
    return {
      id: sale.cycle,
      name: this.cycles().find((item) => item.id === sale.cycle)?.name ?? `Bande ${sale.cycle}`,
    };
  });
  protected readonly canPay = computed(() => {
    const sale = this.sale();
    return sale !== null && sale.status === 'active' && sale.balance > 0;
  });
  // Le serveur refuse d'annuler une vente déjà payée en partie : on n'offre pas le bouton.
  protected readonly canCancel = computed(() => {
    const sale = this.sale();
    return sale !== null && sale.status === 'active' && this.payments().length === 0;
  });
  protected readonly hasPaymentsLock = computed(() => {
    const sale = this.sale();
    return sale !== null && sale.status === 'active' && this.payments().length > 0;
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      sale: this.finance.sale(this.saleId),
      payments: this.finance.payments(this.saleId),
      cycles: this.farming.cycles().pipe(catchError(() => of(EMPTY_CYCLES))),
    }).subscribe({
      next: ({ sale, payments, cycles }) => {
        this.sale.set(sale);
        this.payments.set(payments);
        this.cycles.set(cycles.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Impossible de charger cette vente. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected methodLabel(method: string): string {
    return METHOD_LABELS[method] ?? method;
  }

  protected settle(): void {
    const sale = this.sale();
    if (sale) this.amount.set(String(sale.balance));
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.pay();
  }

  protected pay(): void {
    const sale = this.sale();
    if (!sale || this.saving()) return;
    const amount = parseNumber(this.amount());
    if (!Number.isInteger(amount) || amount <= 0) {
      this.formError.set('Indiquez un montant en francs, supérieur à zéro.');
      return;
    }
    if (amount > sale.balance) {
      this.formError.set(`Le paiement dépasse le reste à payer (${formatMoney(sale.balance)}).`);
      return;
    }
    if (this.payDate() < sale.sale_date) {
      this.formError.set('La date du paiement précède celle de la vente.');
      return;
    }
    this.saving.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.finance
      .recordPayment(sale.id, {
        uuid: this.pendingUuid,
        amount,
        payment_date: this.payDate(),
        method: this.method(),
      })
      .subscribe({
        next: () => {
          this.pendingUuid = newUuid();
          this.amount.set('');
          this.notice.set(`Paiement de ${formatMoney(amount)} enregistré.`);
          this.saving.set(false);
          this.refresh();
        },
        error: (error: unknown) => {
          this.formError.set(
            firstMessage(error, 'L’enregistrement a échoué. Votre saisie est gardée : réessayez.'),
          );
          this.saving.set(false);
        },
      });
  }

  protected askCancel(): void {
    this.cancelError.set(null);
    this.confirming.set(true);
  }

  protected abandonCancel(): void {
    this.confirming.set(false);
  }

  protected cancel(): void {
    const sale = this.sale();
    if (!sale || this.cancelling()) return;
    this.cancelling.set(true);
    this.cancelError.set(null);
    this.finance.cancelSale(sale.id, this.reason().trim()).subscribe({
      next: (cancelled) => {
        this.sale.set(cancelled);
        this.confirming.set(false);
        this.cancelling.set(false);
        this.notice.set('Vente annulée : l’effectif (ou le stock d’œufs) a été remis à jour.');
      },
      error: (error: unknown) => {
        this.cancelError.set(firstMessage(error, 'L’annulation a échoué. Réessayez.'));
        this.cancelling.set(false);
      },
    });
  }

  // Émet (ou retrouve) la facture de la vente, ou le reçu d'un paiement, puis télécharge ou partage le PDF.
  // Le serveur renvoie le même document si on redemande : pas de doublon, pas de trou dans les numéros.
  protected async openDocument(kind: DocumentKind, share: boolean, paymentId?: number): Promise<void> {
    const sale = this.sale();
    if (!sale || this.docBusy() !== null) return;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.docError.set(
        'Pas de connexion : les factures et les reçus se créent en ligne. Réessayez quand le réseau revient.',
      );
      return;
    }
    this.docBusy.set(paymentId === undefined ? kind : `${kind}-${paymentId}`);
    this.docError.set(null);
    const customerName = sale.customer === null ? this.guestName().trim() : '';
    const target = paymentId === undefined ? { kind, sale: sale.id } : { kind, payment: paymentId };
    try {
      const document = await firstValueFrom(
        this.documents.issue(customerName ? { ...target, customer_name: customerName } : target),
      );
      const blob = await firstValueFrom(this.documents.pdf(document));
      const filename = `${document.number}.pdf`;
      const file = new File([blob], filename, { type: 'application/pdf' });
      if (share && this.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], title: document.number });
      } else {
        downloadBlob(blob, filename);
      }
    } catch (error: unknown) {
      // Fermer le menu de partage n'est pas une erreur.
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        this.docError.set(firstMessage(error, 'Le document n’a pas pu être créé. Réessayez dans un instant.'));
      }
    } finally {
      this.docBusy.set(null);
    }
  }

  private refresh(): void {
    forkJoin({
      sale: this.finance.sale(this.saleId),
      payments: this.finance.payments(this.saleId),
    }).subscribe({
      next: ({ sale, payments }) => {
        this.sale.set(sale);
        this.payments.set(payments);
      },
    });
  }
}
