import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { shortDate } from '../../core/dates';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { Receivable, Sale } from '../../core/finance.models';
import { FinanceService } from '../../core/finance.service';
import { formatCompact, formatMoney } from '../../core/money';

const EMPTY_CYCLES: Page<Cycle> = { count: 0, next: null, previous: null, results: [] };

@Component({
  selector: 'app-sales',
  imports: [RouterLink],
  templateUrl: './sales.html',
  styleUrl: './sales.scss',
})
export class Sales {
  private readonly finance = inject(FinanceService);
  private readonly farming = inject(FarmingService);

  protected readonly sales = signal<Sale[]>([]);
  protected readonly receivables = signal<Receivable[]>([]);
  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly hasMore = signal(false);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly money = formatMoney;
  protected readonly compact = formatCompact;
  protected readonly shortDate = shortDate;

  private readonly valid = computed(() => this.sales().filter((sale) => sale.status === 'active'));
  protected readonly totalSold = computed(() =>
    this.valid().reduce((sum, sale) => sum + sale.total_amount, 0),
  );
  protected readonly totalPaid = computed(() =>
    this.valid().reduce((sum, sale) => sum + sale.paid, 0),
  );
  protected readonly totalDue = computed(() =>
    this.receivables().reduce((sum, row) => sum + row.total_due, 0),
  );

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
      page: this.finance.sales(),
      receivables: this.finance.receivables().pipe(catchError(() => of([] as Receivable[]))),
      cycles: this.farming.cycles().pipe(catchError(() => of(EMPTY_CYCLES))),
    }).subscribe({
      next: ({ page, receivables, cycles }) => {
        this.sales.set(page.results);
        this.hasMore.set(page.next !== null);
        this.receivables.set(receivables);
        this.cycles.set(cycles.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Impossible de charger les ventes. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected cycleName(id: number): string {
    return this.cycleNames().get(id) ?? `Bande ${id}`;
  }
}
