import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { dayNumber } from '../../core/dates';
import { Cycle, CycleStatus } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { formatNumber } from '../../core/money';

const STATUS_LABELS: Record<CycleStatus, string> = {
  planned: 'Planifiée',
  active: 'En cours',
  completed: 'Terminée',
  cancelled: 'Annulée',
};

const STATUS_TONES: Record<CycleStatus, 'ok' | 'warn' | 'done' | 'danger'> = {
  planned: 'warn',
  active: 'ok',
  completed: 'done',
  cancelled: 'danger',
};

@Component({
  selector: 'app-cycles',
  imports: [RouterLink],
  templateUrl: './cycles.html',
  styleUrl: './cycles.scss',
})
export class Cycles {
  private readonly service = inject(FarmingService);
  private readonly auth = inject(AuthService);

  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly total = signal(0);
  protected readonly coopNames = signal<Record<number, string>>({});
  protected readonly filter = signal<'active' | 'all'>('active');
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly number = formatNumber;
  protected readonly day = dayNumber;
  protected readonly canCreate = computed(() => this.auth.can('manage_cycles'));

  protected readonly visible = computed(() =>
    this.filter() === 'active'
      ? this.cycles().filter((cycle) => cycle.status === 'active')
      : this.cycles(),
  );

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({ cycles: this.service.cycles(), coops: this.service.coops() }).subscribe({
      next: ({ cycles, coops }) => {
        this.cycles.set(cycles.results);
        this.total.set(cycles.count);
        this.coopNames.set(Object.fromEntries(coops.results.map((coop) => [coop.id, coop.name])));
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(
          error instanceof HttpErrorResponse && error.status === 0
            ? 'Pas de connexion. Réessayez quand le réseau revient.'
            : 'Impossible de charger les bandes. Réessayez dans un instant.',
        );
        this.loading.set(false);
      },
    });
  }

  protected statusLabel(cycle: Cycle): string {
    return STATUS_LABELS[cycle.status];
  }

  protected tone(cycle: Cycle): string {
    return STATUS_TONES[cycle.status];
  }

  // Part des poulets de départ encore en vie ou vendus : sert à remplir la barre.
  protected alivePercent(cycle: Cycle): number {
    if (cycle.initial_count <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((cycle.current_count / cycle.initial_count) * 100)));
  }
}
