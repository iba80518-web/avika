import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { firstMessage } from '../../core/api-errors';
import { localToday, shortDate } from '../../core/dates';
import { Cycle, Page } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { InventoryService } from '../../core/inventory.service';
import { NewMovement, Product, StockMovement } from '../../core/inventory.models';
import { formatMoney } from '../../core/money';
import { formatQuantity } from '../../core/quantity';
import { newUuid } from '../../core/uuid';

type Kind = 'entry' | 'exit' | 'loss';

const MOVEMENT_LABELS: Record<string, string> = {
  entry: 'Entrée',
  exit: 'Sortie',
  loss: 'Perte',
  adjustment: 'Ajustement',
};

const EMPTY_CYCLES: Page<Cycle> = { count: 0, next: null, previous: null, results: [] };

@Component({
  selector: 'app-stock-detail',
  imports: [RouterLink],
  templateUrl: './stock-detail.html',
  styleUrl: './stock-detail.scss',
})
export class StockDetail {
  private readonly inventory = inject(InventoryService);
  private readonly farming = inject(FarmingService);
  private readonly productId = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));

  protected readonly kinds: { value: Kind; label: string }[] = [
    { value: 'exit', label: 'Sortie' },
    { value: 'entry', label: 'Entrée' },
    { value: 'loss', label: 'Perte' },
  ];
  protected readonly today = localToday();

  protected readonly product = signal<Product | null>(null);
  protected readonly movements = signal<StockMovement[]>([]);
  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly kind = signal<Kind>('exit');
  protected readonly quantity = signal('');
  protected readonly cost = signal('');
  protected readonly cycleId = signal<number | null>(null);
  protected readonly date = signal(localToday());
  protected readonly note = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  // Gardé tant que la saisie n'a pas réussi : un nouvel essai ne peut pas créer de doublon.
  private pendingUuid = newUuid();

  protected readonly qty = formatQuantity;
  protected readonly money = formatMoney;
  protected readonly shortDate = shortDate;

  protected readonly activeCycles = computed(() =>
    this.cycles().filter((cycle) => cycle.status === 'active'),
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
      product: this.inventory.product(this.productId),
      movements: this.inventory.movements(this.productId),
      // Sans droit sur les bandes, on peut quand même gérer le stock : la liste des bandes reste vide.
      cycles: this.farming.cycles().pipe(catchError(() => of(EMPTY_CYCLES))),
    }).subscribe({
      next: ({ product, movements, cycles }) => {
        this.product.set(product);
        this.movements.set(movements.results);
        this.cycles.set(cycles.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Impossible de charger ce produit. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected pickKind(kind: Kind): void {
    this.kind.set(kind);
    this.formError.set(null);
  }

  protected onQuantity(event: Event): void {
    this.quantity.set((event.target as HTMLInputElement).value);
  }

  protected onCost(event: Event): void {
    this.cost.set((event.target as HTMLInputElement).value);
  }

  protected onDate(event: Event): void {
    this.date.set((event.target as HTMLInputElement).value);
  }

  protected onNote(event: Event): void {
    this.note.set((event.target as HTMLInputElement).value);
  }

  protected onCycle(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.cycleId.set(value === '' ? null : Number(value));
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    this.save();
  }

  protected save(): void {
    const product = this.product();
    if (!product || this.saving()) return;

    const quantity = Number(this.quantity().replace(/\s/g, '').replace(',', '.'));
    if (!Number.isFinite(quantity) || quantity <= 0) {
      this.formError.set('Indiquez une quantité supérieure à zéro.');
      return;
    }
    const kind = this.kind();
    if (kind !== 'entry' && quantity > Number(product.stock)) {
      this.formError.set(
        `Stock insuffisant : il reste ${formatQuantity(product.stock)} ${product.base_unit}.`,
      );
      return;
    }

    const body: NewMovement = {
      movement_type: kind,
      quantity,
      movement_date: this.date(),
      note: this.note().trim(),
      uuid: this.pendingUuid,
    };
    if (kind === 'entry') {
      const raw = this.cost().replace(/\s/g, '');
      const cost = Number(raw);
      if (raw === '' || !Number.isInteger(cost) || cost < 0) {
        this.formError.set('Indiquez le coût total de l’achat en francs (0 si c’est gratuit).');
        return;
      }
      body.total_cost = cost;
    }
    const cycle = this.cycleId();
    if (kind === 'exit' && cycle !== null) {
      body.cycle = cycle;
    }

    this.saving.set(true);
    this.formError.set(null);
    this.notice.set(null);
    this.inventory.recordMovement(product.id, body).subscribe({
      next: () => {
        this.pendingUuid = newUuid();
        this.quantity.set('');
        this.cost.set('');
        this.note.set('');
        this.cycleId.set(null);
        this.notice.set(`${MOVEMENT_LABELS[kind]} de ${formatQuantity(quantity)} ${product.base_unit} enregistrée.`);
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

  private refresh(): void {
    forkJoin({
      product: this.inventory.product(this.productId),
      movements: this.inventory.movements(this.productId),
    }).subscribe({
      next: ({ product, movements }) => {
        this.product.set(product);
        this.movements.set(movements.results);
      },
    });
  }

  protected movementLabel(movement: StockMovement): string {
    return MOVEMENT_LABELS[movement.movement_type] ?? movement.movement_type;
  }

  protected signed(movement: StockMovement): string {
    const value = Number(movement.base_quantity);
    const negative =
      movement.movement_type === 'exit' || movement.movement_type === 'loss' || value < 0;
    return `${negative ? '−' : '+'}${formatQuantity(Math.abs(value))}`;
  }

  protected cycleName(movement: StockMovement): string {
    return movement.cycle === null ? '' : (this.cycleNames().get(movement.cycle) ?? `Bande ${movement.cycle}`);
  }
}
