import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday } from '../../core/dates';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { HEALTH_KINDS, HealthKind, HealthTemplate } from '../../core/health.models';
import { HealthService } from '../../core/health.service';
import { InventoryService } from '../../core/inventory.service';
import { Product } from '../../core/inventory.models';
import { newUuid } from '../../core/uuid';

type Mode = 'task' | 'schedule';

const emptyPage = <T>(): Page<T> => ({ count: 0, next: null, previous: null, results: [] });

@Component({
  selector: 'app-health-form',
  imports: [RouterLink],
  templateUrl: './health-form.html',
  styleUrl: './health-form.scss',
})
export class HealthForm {
  private readonly service = inject(HealthService);
  private readonly farming = inject(FarmingService);
  private readonly inventory = inject(InventoryService);
  private readonly router = inject(Router);

  protected readonly kinds = HEALTH_KINDS;

  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly products = signal<Product[]>([]);
  protected readonly templates = signal<HealthTemplate[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly mode = signal<Mode>('task');
  protected readonly cycleId = signal('');
  protected readonly name = signal('');
  protected readonly kind = signal<HealthKind>('vaccine');
  protected readonly dueDate = signal(localToday());
  protected readonly productId = signal('');
  protected readonly note = signal('');
  protected readonly templateId = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  // Gardé tant que l'envoi n'a pas réussi : un nouvel essai ne peut pas créer une seconde tâche.
  private pendingUuid = newUuid();

  protected readonly activeCycles = computed(() =>
    this.cycles().filter((cycle) => cycle.status === 'active'),
  );
  protected readonly activeProducts = computed(() =>
    this.products().filter((product) => product.is_active),
  );
  protected readonly activeTemplates = computed(() =>
    this.templates().filter((template) => template.is_active),
  );

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    forkJoin({
      cycles: this.farming.cycles(),
      // Sans droit sur le stock ou sans calendrier, on peut quand même créer une tâche simple.
      products: this.inventory.products().pipe(catchError(() => of(emptyPage<Product>()))),
      templates: this.service.templates().pipe(catchError(() => of(emptyPage<HealthTemplate>()))),
    }).subscribe({
      next: ({ cycles, products, templates }) => {
        this.cycles.set(cycles.results);
        this.products.set(products.results);
        this.templates.set(templates.results);
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

  protected pickMode(mode: Mode): void {
    this.mode.set(mode);
    this.formError.set(null);
    this.notice.set(null);
  }

  protected itemCount(template: HealthTemplate): number {
    return Array.isArray(template.items) ? template.items.length : 0;
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    if (this.mode() === 'task') {
      this.saveTask();
    } else {
      this.saveSchedule();
    }
  }

  private saveTask(): void {
    if (this.saving()) return;
    if (this.cycleId() === '') {
      this.formError.set('Choisissez la bande concernée.');
      return;
    }
    const name = this.name().trim();
    if (name === '') {
      this.formError.set('Indiquez le nom de la tâche (ex. Vaccin Newcastle).');
      return;
    }
    if (this.dueDate() === '') {
      this.formError.set('Indiquez la date prévue.');
      return;
    }
    this.saving.set(true);
    this.formError.set(null);
    this.service
      .createTask({
        uuid: this.pendingUuid,
        cycle: Number(this.cycleId()),
        name,
        kind: this.kind(),
        due_date: this.dueDate(),
        note: this.note().trim(),
        ...(this.productId() === '' ? {} : { product: Number(this.productId()) }),
      })
      .subscribe({
        next: () => void this.router.navigate(['/sante']),
        error: (error: unknown) => {
          this.formError.set(
            firstMessage(error, 'L’enregistrement a échoué. Votre saisie est gardée : réessayez.'),
          );
          this.saving.set(false);
        },
      });
  }

  private saveSchedule(): void {
    if (this.saving()) return;
    if (this.cycleId() === '') {
      this.formError.set('Choisissez la bande concernée.');
      return;
    }
    if (this.templateId() === '') {
      this.formError.set('Choisissez un calendrier type.');
      return;
    }
    this.saving.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.service
      .schedule({ cycle: Number(this.cycleId()), template: Number(this.templateId()) })
      .subscribe({
        next: (tasks) => {
          if (tasks.length === 0) {
            this.notice.set('Ce calendrier est déjà planifié pour cette bande : rien n’a été ajouté.');
            this.saving.set(false);
          } else {
            void this.router.navigate(['/sante']);
          }
        },
        error: (error: unknown) => {
          this.formError.set(firstMessage(error, 'La planification a échoué. Réessayez.'));
          this.saving.set(false);
        },
      });
  }
}
