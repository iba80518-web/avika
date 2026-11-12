import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { shortDate } from '../../core/dates';
import { categoryLabel, Expense } from '../../core/expense.models';
import { ExpenseService } from '../../core/expense.service';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { formatCompact, formatMoney } from '../../core/money';

const EMPTY_CYCLES: Page<Cycle> = { count: 0, next: null, previous: null, results: [] };

@Component({
  selector: 'app-expenses',
  imports: [RouterLink],
  templateUrl: './expenses.html',
  styleUrl: './expenses.scss',
})
export class Expenses {
  private readonly service = inject(ExpenseService);
  private readonly farming = inject(FarmingService);

  protected readonly expenses = signal<Expense[]>([]);
  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly hasMore = signal(false);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly money = formatMoney;
  protected readonly compact = formatCompact;
  protected readonly shortDate = shortDate;
  protected readonly label = categoryLabel;

  protected readonly total = computed(() =>
    this.expenses().reduce((sum, expense) => sum + expense.amount, 0),
  );

  protected readonly byCategory = computed(() => {
    const totals = new Map<string, number>();
    for (const expense of this.expenses()) {
      totals.set(expense.category, (totals.get(expense.category) ?? 0) + expense.amount);
    }
    const max = Math.max(0, ...totals.values());
    return Array.from(totals, ([category, total]) => ({
      category,
      label: categoryLabel(category),
      total,
      percent: max > 0 ? Math.round((total / max) * 100) : 0,
    })).sort((a, b) => b.total - a.total);
  });

  private readonly cycleNames = computed(
    () => new Map(this.cycles().map((cycle) => [cycle.id, cycle.name] as const)),
  );

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      page: this.service.list(),
      cycles: this.farming.cycles().pipe(catchError(() => of(EMPTY_CYCLES))),
    }).subscribe({
      next: ({ page, cycles }) => {
        this.expenses.set(page.results);
        this.hasMore.set(page.next !== null);
        this.cycles.set(cycles.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Impossible de charger les dépenses. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected cycleName(id: number | null): string {
    if (id === null) return 'Dépense générale';
    return this.cycleNames().get(id) ?? `Bande ${id}`;
  }
}
