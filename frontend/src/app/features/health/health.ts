import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday, shortDate } from '../../core/dates';
import { HealthStatus, HealthTask, kindLabel, Reminders } from '../../core/health.models';
import { HealthService } from '../../core/health.service';
import { parseNumber } from '../../core/numbers';

type Filter = 'planned' | 'done' | 'all';
type Tone = 'warn' | 'info' | 'ok' | 'grey';

const EMPTY_REMINDERS: Reminders = { overdue: [], today: [], tomorrow: [] };

function nextDay(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number);
  const date = new Date(year, month - 1, day + 1);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

@Component({
  selector: 'app-health',
  imports: [RouterLink],
  templateUrl: './health.html',
  styleUrl: './health.scss',
})
export class Health {
  private readonly service = inject(HealthService);

  protected readonly filters: { value: Filter; label: string }[] = [
    { value: 'planned', label: 'À faire' },
    { value: 'done', label: 'Faites' },
    { value: 'all', label: 'Toutes' },
  ];
  protected readonly today = localToday();
  private readonly tomorrow = nextDay(this.today);
  protected readonly shortDate = shortDate;
  protected readonly kind = kindLabel;

  protected readonly tasks = signal<HealthTask[]>([]);
  protected readonly reminders = signal<Reminders>(EMPTY_REMINDERS);
  protected readonly filter = signal<Filter>('planned');
  protected readonly hasMore = signal(false);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  protected readonly openId = signal<number | null>(null);
  protected readonly doneDate = signal(localToday());
  protected readonly doneQty = signal('');
  protected readonly useStock = signal(false);
  protected readonly completing = signal(false);
  protected readonly completeError = signal<string | null>(null);

  protected readonly cancelId = signal<number | null>(null);
  protected readonly cancelling = signal(false);
  protected readonly cancelError = signal<string | null>(null);

  protected readonly counts = computed(() => ({
    overdue: this.reminders().overdue.length,
    today: this.reminders().today.length,
    tomorrow: this.reminders().tomorrow.length,
  }));

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.fetch(true);
  }

  private refresh(): void {
    this.fetch(false);
  }

  private fetch(first: boolean): void {
    const filter = this.filter();
    const status: HealthStatus | undefined = filter === 'all' ? undefined : filter;
    forkJoin({
      page: this.service.tasks(status),
      reminders: this.service.reminders().pipe(catchError(() => of(EMPTY_REMINDERS))),
    }).subscribe({
      next: ({ page, reminders }) => {
        this.tasks.set(page.results);
        this.hasMore.set(page.next !== null);
        this.reminders.set(reminders);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        if (first) {
          this.error.set(firstMessage(error, 'Impossible de charger la santé. Réessayez dans un instant.'));
        }
        this.loading.set(false);
      },
    });
  }

  protected setFilter(filter: Filter): void {
    this.filter.set(filter);
    this.closePanels();
    this.load();
  }

  protected badge(task: HealthTask): { text: string; tone: Tone } {
    if (task.status === 'done') return { text: 'Réalisée', tone: 'ok' };
    if (task.status === 'cancelled') return { text: 'Annulée', tone: 'grey' };
    if (task.due_date < this.today) return { text: 'En retard', tone: 'warn' };
    if (task.due_date === this.today) return { text: 'Aujourd’hui', tone: 'info' };
    if (task.due_date === this.tomorrow) return { text: 'Demain', tone: 'info' };
    return { text: shortDate(task.due_date), tone: 'grey' };
  }

  private closePanels(): void {
    this.openId.set(null);
    this.cancelId.set(null);
    this.completeError.set(null);
    this.cancelError.set(null);
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected startComplete(task: HealthTask): void {
    this.closePanels();
    this.notice.set(null);
    this.doneDate.set(localToday());
    this.doneQty.set('');
    this.useStock.set(false);
    this.openId.set(task.id);
  }

  protected abandonComplete(): void {
    this.openId.set(null);
    this.completeError.set(null);
  }

  protected onComplete(event: Event, task: HealthTask): void {
    event.preventDefault();
    this.complete(task);
  }

  protected complete(task: HealthTask): void {
    if (this.completing()) return;
    if (this.doneDate() === '') {
      this.completeError.set('Indiquez la date de réalisation.');
      return;
    }
    if (this.doneDate() > this.today) {
      this.completeError.set('La date de réalisation ne peut pas être dans le futur.');
      return;
    }
    const raw = this.doneQty().trim();
    const quantity = parseNumber(raw);
    if (raw !== '' && !(quantity > 0)) {
      this.completeError.set('La quantité doit être supérieure à 0.');
      return;
    }
    const withStock = this.useStock() && task.product !== null;
    if (withStock && raw === '') {
      this.completeError.set('Indiquez la quantité utilisée pour retirer du stock.');
      return;
    }

    this.completing.set(true);
    this.completeError.set(null);
    this.service
      .complete(task.id, {
        done_date: this.doneDate(),
        use_stock: withStock,
        ...(raw === '' ? {} : { quantity }),
      })
      .subscribe({
        next: () => {
          this.notice.set(`« ${task.name} » est marquée comme réalisée.`);
          this.openId.set(null);
          this.completing.set(false);
          this.refresh();
        },
        error: (error: unknown) => {
          this.completeError.set(firstMessage(error, 'L’enregistrement a échoué. Réessayez.'));
          this.completing.set(false);
        },
      });
  }

  protected askCancel(task: HealthTask): void {
    this.closePanels();
    this.notice.set(null);
    this.cancelId.set(task.id);
  }

  protected abandonCancel(): void {
    this.cancelId.set(null);
    this.cancelError.set(null);
  }

  protected cancel(task: HealthTask): void {
    if (this.cancelling()) return;
    this.cancelling.set(true);
    this.cancelError.set(null);
    this.service.cancel(task.id).subscribe({
      next: () => {
        this.notice.set(`« ${task.name} » est annulée.`);
        this.cancelId.set(null);
        this.cancelling.set(false);
        this.refresh();
      },
      error: (error: unknown) => {
        this.cancelError.set(firstMessage(error, 'L’annulation a échoué. Réessayez.'));
        this.cancelling.set(false);
      },
    });
  }
}
