import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { catchError, forkJoin, Observable, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday } from '../../core/dates';
import {
  EXPENSE_CATEGORIES,
  Expense,
  ExpenseCategory,
} from '../../core/expense.models';
import { ExpenseService } from '../../core/expense.service';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { parseNumber } from '../../core/numbers';
import { newUuid } from '../../core/uuid';

const EMPTY_CYCLES: Page<Cycle> = { count: 0, next: null, previous: null, results: [] };

@Component({
  selector: 'app-expense-form',
  imports: [RouterLink],
  templateUrl: './expense-form.html',
  styleUrl: './expense-form.scss',
})
export class ExpenseForm {
  private readonly service = inject(ExpenseService);
  private readonly farming = inject(FarmingService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  // Pas d'identifiant dans l'adresse : nouvelle dépense. Sinon : correction d'une dépense existante.
  protected readonly expenseId: number | null = this.route.snapshot.paramMap.get('id') === null
    ? null
    : Number(this.route.snapshot.paramMap.get('id'));
  protected readonly categories = EXPENSE_CATEGORIES;
  protected readonly today = localToday();

  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly amount = signal('');
  protected readonly date = signal(localToday());
  protected readonly category = signal<ExpenseCategory | null>(null);
  protected readonly cycleId = signal('');
  protected readonly description = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);

  // Gardé tant que l'envoi n'a pas réussi : un nouvel essai ne peut pas créer une seconde dépense.
  private pendingUuid = newUuid();

  // Une bande annulée refuse les dépenses, sauf si c'est celle déjà liée à cette dépense.
  protected readonly choosableCycles = computed(() =>
    this.cycles().filter((cycle) => cycle.status !== 'cancelled' || String(cycle.id) === this.cycleId()),
  );

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    const expense$: Observable<Expense | null> =
      this.expenseId === null ? of(null) : this.service.get(this.expenseId);
    forkJoin({
      expense: expense$,
      cycles: this.farming.cycles().pipe(catchError(() => of(EMPTY_CYCLES))),
    }).subscribe({
      next: ({ expense, cycles }) => {
        this.cycles.set(cycles.results);
        if (expense) {
          this.amount.set(String(expense.amount));
          this.date.set(expense.expense_date);
          this.category.set(expense.category);
          this.cycleId.set(expense.cycle === null ? '' : String(expense.cycle));
          this.description.set(expense.description);
        }
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(firstMessage(error, 'Impossible de charger cette dépense. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.save();
  }

  protected save(): void {
    if (this.saving()) return;
    const category = this.category();
    if (category === null) {
      this.formError.set('Choisissez une catégorie.');
      return;
    }
    const amount = parseNumber(this.amount());
    if (!Number.isInteger(amount) || amount < 1) {
      this.formError.set('Indiquez le montant en francs (nombre entier supérieur à 0).');
      return;
    }
    if (this.date() === '') {
      this.formError.set('Indiquez la date de la dépense.');
      return;
    }
    const cycle = this.cycleId() === '' ? null : Number(this.cycleId());
    const description = this.description().trim();

    this.saving.set(true);
    this.formError.set(null);
    const request$ =
      this.expenseId === null
        ? this.service.create({
            uuid: this.pendingUuid,
            amount,
            expense_date: this.date(),
            category,
            description,
            ...(cycle === null ? {} : { cycle }),
          })
        : this.service.update(this.expenseId, {
            amount,
            expense_date: this.date(),
            category,
            description,
            cycle,
          });
    request$.subscribe({
      next: () => void this.router.navigate(['/depenses']),
      error: (error: unknown) => {
        this.formError.set(
          firstMessage(error, 'L’enregistrement a échoué. Votre saisie est gardée : réessayez.'),
        );
        this.saving.set(false);
      },
    });
  }
}
