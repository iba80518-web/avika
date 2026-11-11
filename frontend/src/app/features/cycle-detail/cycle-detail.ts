import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { AuthService } from '../../core/auth.service';
import { dayNumber, localToday, shortDate } from '../../core/dates';
import { Cycle, CycleSummary, EventType, FlockEvent } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { formatNumber } from '../../core/money';
import { newUuid } from '../../core/uuid';

const EVENT_LABELS: Record<EventType, string> = {
  entry: 'Entrée',
  mortality: 'Mortalité',
  sale: 'Vente',
  transfer_in: 'Transfert reçu',
  transfer_out: 'Transfert sorti',
  correction: 'Correction',
};

const NEGATIVE: EventType[] = ['mortality', 'sale', 'transfer_out'];

const STATUS_LABELS: Record<string, string> = {
  planned: 'Planifiée',
  active: 'En cours',
  completed: 'Terminée',
  cancelled: 'Annulée',
};

@Component({
  selector: 'app-cycle-detail',
  imports: [RouterLink],
  templateUrl: './cycle-detail.html',
  styleUrl: './cycle-detail.scss',
})
export class CycleDetail {
  private readonly service = inject(FarmingService);
  private readonly auth = inject(AuthService);
  private readonly cycleId = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));

  protected readonly causes = ['Chaleur', 'Maladie', 'Écrasement', 'Prédateur', 'Inconnue'];
  protected readonly today = localToday();

  protected readonly cycle = signal<Cycle | null>(null);
  protected readonly summary = signal<CycleSummary | null>(null);
  protected readonly events = signal<FlockEvent[]>([]);
  protected readonly coopName = signal('');
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly quantity = signal(1);
  protected readonly cause = signal('');
  protected readonly date = signal(localToday());
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  // Gardé tant que la saisie n'a pas réussi : un nouvel essai ne peut pas créer de doublon.
  private pendingUuid = newUuid();

  protected readonly number = formatNumber;
  protected readonly day = dayNumber;
  protected readonly shortDate = shortDate;

  protected readonly canRecord = computed(
    () => this.cycle()?.status === 'active' && this.auth.can('record_mortality'),
  );

  protected readonly statusLabel = computed(() => STATUS_LABELS[this.cycle()?.status ?? ''] ?? '');

  protected readonly mortalityTone = computed(() => {
    const rate = this.summary()?.mortality_rate ?? 0;
    return rate >= 8 ? 'danger' : rate >= 5 ? 'warn' : 'ok';
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({
      cycle: this.service.cycle(this.cycleId),
      summary: this.service.summary(this.cycleId),
      events: this.service.events(this.cycleId),
      coops: this.service.coops(),
    }).subscribe({
      next: ({ cycle, summary, events, coops }) => {
        this.cycle.set(cycle);
        this.summary.set(summary);
        this.events.set(events.results);
        const coop = coops.results.find((item) => item.id === cycle.coop);
        this.coopName.set(coop?.name ?? '');
        this.coopCapacity.set(coop?.capacity ?? 0);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(
          error instanceof HttpErrorResponse && error.status === 404
            ? 'Cette bande est introuvable.'
            : error instanceof HttpErrorResponse && error.status === 0
              ? 'Pas de connexion. Réessayez quand le réseau revient.'
              : 'Impossible de charger la bande. Réessayez dans un instant.',
        );
        this.loading.set(false);
      },
    });
  }

  protected step(delta: number): void {
    this.quantity.set(Math.max(1, this.quantity() + delta));
  }

  protected onQuantity(event: Event): void {
    const value = Math.floor(Number((event.target as HTMLInputElement).value));
    this.quantity.set(Number.isFinite(value) ? value : 0);
  }

  protected onDate(event: Event): void {
    this.date.set((event.target as HTMLInputElement).value);
  }

  protected pickCause(cause: string): void {
    this.cause.set(this.cause() === cause ? '' : cause);
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.save();
  }

  protected save(): void {
    const cycle = this.cycle();
    if (!cycle || this.saving()) return;
    const quantity = this.quantity();
    if (!Number.isInteger(quantity) || quantity < 1) {
      this.formError.set('Indiquez un nombre de morts supérieur à zéro.');
      return;
    }
    this.saving.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.service
      .recordMortality(cycle.id, {
        event_type: 'mortality',
        quantity,
        event_date: this.date(),
        cause: this.cause(),
        uuid: this.pendingUuid,
      })
      .subscribe({
        next: () => {
          this.pendingUuid = newUuid();
          this.quantity.set(1);
          this.cause.set('');
          this.notice.set(`${quantity} mortalité(s) enregistrée(s).`);
          this.saving.set(false);
          this.refresh();
        },
        error: (error: unknown) => {
          this.formError.set(this.messageFor(error));
          this.saving.set(false);
        },
      });
  }

  // Après une saisie : on relit seulement le résumé et l'historique.
  private refresh(): void {
    forkJoin({
      summary: this.service.summary(this.cycleId),
      events: this.service.events(this.cycleId),
    }).subscribe({
      next: ({ summary, events }) => {
        this.summary.set(summary);
        this.events.set(events.results);
        const cycle = this.cycle();
        if (cycle) this.cycle.set({ ...cycle, current_count: summary.current_count });
      },
    });
  }

  // ---------- Démarrer, terminer, annuler ----------
  protected readonly coopCapacity = signal(0);
  protected readonly pending = signal<'start' | 'complete' | 'cancel' | null>(null);
  protected readonly acting = signal(false);
  protected readonly actionError = signal<string | null>(null);

  protected readonly canManage = computed(() => this.auth.can('manage_cycles'));
  protected readonly overCapacity = computed(() => {
    const cycle = this.cycle();
    const capacity = this.coopCapacity();
    return !!cycle && capacity > 0 && cycle.initial_count > capacity;
  });

  protected ask(action: 'start' | 'complete' | 'cancel'): void {
    this.actionError.set(null);
    this.pending.set(action);
  }

  protected dismiss(): void {
    this.pending.set(null);
    this.actionError.set(null);
  }

  protected confirm(): void {
    const action = this.pending();
    const cycle = this.cycle();
    if (!action || !cycle || this.acting()) return;
    this.acting.set(true);
    this.actionError.set(null);
    const call =
      action === 'start'
        ? this.service.startCycle(cycle.id, this.overCapacity())
        : action === 'complete'
          ? this.service.completeCycle(cycle.id)
          : this.service.cancelCycle(cycle.id);
    call.subscribe({
      next: (updated) => {
        this.cycle.set(updated);
        this.pending.set(null);
        this.acting.set(false);
        this.refresh();
      },
      error: (error: unknown) => {
        this.actionError.set(firstMessage(error));
        this.acting.set(false);
      },
    });
  }

  protected eventLabel(event: FlockEvent): string {
    return EVENT_LABELS[event.event_type];
  }

  protected signed(event: FlockEvent): string {
    const negative = NEGATIVE.includes(event.event_type);
    return `${negative ? '−' : '+'}${formatNumber(event.quantity)}`;
  }

  private messageFor(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        return 'Pas de connexion. Votre saisie est gardée : appuyez de nouveau sur Enregistrer quand le réseau revient.';
      }
      if (error.status === 403) {
        return 'Vous n’avez pas le droit d’enregistrer une mortalité.';
      }
      const body: unknown = error.error;
      if (body && typeof body === 'object') {
        const first = Object.values(body as Record<string, unknown>)[0];
        const text = Array.isArray(first) ? first[0] : first;
        if (typeof text === 'string') return text;
      }
    }
    return 'L’enregistrement a échoué. Réessayez dans un instant.';
  }
}
