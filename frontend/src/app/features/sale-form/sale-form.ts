import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday } from '../../core/dates';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { Customer, NewSale, PaymentMethod, SaleType } from '../../core/finance.models';
import { FinanceService } from '../../core/finance.service';
import { formatMoney } from '../../core/money';
import { parseNumber } from '../../core/numbers';
import { newUuid } from '../../core/uuid';

const emptyPage = <T>(): Page<T> => ({ count: 0, next: null, previous: null, results: [] });

@Component({
  selector: 'app-sale-form',
  imports: [RouterLink],
  templateUrl: './sale-form.html',
  styleUrl: './sale-form.scss',
})
export class SaleForm {
  private readonly finance = inject(FinanceService);
  private readonly farming = inject(FarmingService);
  private readonly router = inject(Router);

  protected readonly types: { value: SaleType; label: string }[] = [
    { value: 'count', label: 'Au nombre' },
    { value: 'weight', label: 'Au poids' },
  ];
  protected readonly methods: { value: PaymentMethod; label: string }[] = [
    { value: 'cash', label: 'Espèces' },
    { value: 'mobile_money', label: 'Mobile money' },
    { value: 'bank_transfer', label: 'Virement' },
    { value: 'other', label: 'Autre' },
  ];
  protected readonly today = localToday();
  protected readonly money = formatMoney;

  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly customers = signal<Customer[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly cycleId = signal('');
  protected readonly type = signal<SaleType>('count');
  protected readonly quantity = signal('');
  protected readonly weight = signal('');
  protected readonly price = signal('');
  protected readonly paid = signal('');
  protected readonly customerId = signal('');
  protected readonly method = signal<PaymentMethod>('cash');
  protected readonly date = signal(localToday());
  protected readonly note = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  // Gardé tant que l'envoi n'a pas réussi : un nouvel essai ne peut pas créer une seconde vente.
  private pendingUuid = newUuid();

  protected readonly activeCycles = computed(() =>
    this.cycles().filter((cycle) => cycle.status === 'active'),
  );
  protected readonly activeCustomers = computed(() =>
    this.customers().filter((customer) => customer.is_active),
  );
  protected readonly selectedCycle = computed(
    () => this.activeCycles().find((cycle) => String(cycle.id) === this.cycleId()) ?? null,
  );

  // Même calcul que le serveur : poids × prix au kg, ou nombre × prix. Le serveur refait le sien.
  protected readonly total = computed(() => {
    const price = parseNumber(this.price());
    const base = this.type() === 'weight' ? parseNumber(this.weight()) : parseNumber(this.quantity());
    const value = Math.round(base * price);
    return Number.isFinite(value) && value > 0 ? value : 0;
  });

  // Champ vide = payé en totalité. 0 écrit = rien payé pour l'instant.
  protected readonly paidValue = computed(() =>
    this.paid().trim() === '' ? this.total() : parseNumber(this.paid()),
  );
  protected readonly balance = computed(() => Math.max(0, this.total() - this.paidValue()));

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    forkJoin({
      cycles: this.farming.cycles(),
      // Sans droit sur les clients, on peut encore vendre au comptant : la liste reste vide.
      customers: this.finance.customers().pipe(catchError(() => of(emptyPage<Customer>()))),
    }).subscribe({
      next: ({ cycles, customers }) => {
        this.cycles.set(cycles.results);
        this.customers.set(customers.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(firstMessage(error, 'Impossible de charger les bandes. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected pickType(type: SaleType): void {
    this.type.set(type);
    this.formError.set(null);
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.save();
  }

  protected save(): void {
    if (this.saving()) return;
    const cycle = this.selectedCycle();
    if (!cycle) {
      this.formError.set('Choisissez la bande vendue.');
      return;
    }
    const quantity = parseNumber(this.quantity());
    if (!Number.isInteger(quantity) || quantity < 1) {
      this.formError.set('Indiquez le nombre de poulets vendus (au moins 1).');
      return;
    }
    if (quantity > cycle.current_count) {
      this.formError.set(`Il ne reste que ${cycle.current_count} poulets dans cette bande.`);
      return;
    }
    const weight = parseNumber(this.weight());
    if (this.type() === 'weight' && !(weight > 0)) {
      this.formError.set('Indiquez le poids total en kg pour une vente au poids.');
      return;
    }
    const price = parseNumber(this.price());
    if (!Number.isInteger(price) || price < 1) {
      this.formError.set('Indiquez le prix en francs (nombre entier supérieur à 0).');
      return;
    }
    const total = this.total();
    const paid = this.paidValue();
    if (total <= 0) {
      this.formError.set('Le montant total de la vente doit être supérieur à 0.');
      return;
    }
    if (!Number.isInteger(paid) || paid < 0 || paid > total) {
      this.formError.set('Le montant payé doit être compris entre 0 et le total de la vente.');
      return;
    }
    const customer = this.customerId();
    if (paid < total && customer === '') {
      this.formError.set('Choisissez un client : une vente non payée en totalité doit en avoir un.');
      return;
    }

    const body: NewSale = {
      uuid: this.pendingUuid,
      cycle: cycle.id,
      sale_date: this.date(),
      sale_type: this.type(),
      quantity,
      unit_price: price,
      paid_amount: paid,
      payment_method: this.method(),
      note: this.note().trim(),
    };
    if (customer !== '') body.customer = Number(customer);
    if (this.type() === 'weight') body.weight_kg = weight;

    this.saving.set(true);
    this.formError.set(null);
    this.finance.recordSale(body).subscribe({
      next: (sale) => void this.router.navigate(['/ventes', sale.id]),
      error: (error: unknown) => {
        this.formError.set(
          firstMessage(error, 'L’enregistrement a échoué. Votre saisie est gardée : réessayez.'),
        );
        this.saving.set(false);
      },
    });
  }
}
