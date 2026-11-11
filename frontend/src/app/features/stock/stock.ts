import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { firstMessage } from '../../core/api-errors';
import { InventoryService } from '../../core/inventory.service';
import { Product, ProductType } from '../../core/inventory.models';
import { formatCompact, formatMoney } from '../../core/money';
import { formatQuantity, levelPercent } from '../../core/quantity';

const TYPE_LABELS: Record<ProductType, string> = {
  feed: 'Aliments',
  vaccine: 'Vaccins',
  medicine: 'Médicaments',
  equipment: 'Équipement',
  packaging: 'Emballages',
  other: 'Autres',
};

const TYPE_ORDER: ProductType[] = ['feed', 'vaccine', 'medicine', 'equipment', 'packaging', 'other'];

@Component({
  selector: 'app-stock',
  imports: [RouterLink],
  templateUrl: './stock.html',
  styleUrl: './stock.scss',
})
export class Stock {
  private readonly service = inject(InventoryService);

  protected readonly products = signal<Product[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly qty = formatQuantity;
  protected readonly money = formatMoney;
  protected readonly compact = formatCompact;

  private readonly active = computed(() => this.products().filter((product) => product.is_active));

  protected readonly groups = computed(() =>
    TYPE_ORDER.map((type) => ({
      type,
      label: TYPE_LABELS[type],
      items: this.active().filter((product) => product.product_type === type),
    })).filter((group) => group.items.length > 0),
  );

  protected readonly totalValue = computed(() =>
    this.active().reduce((sum, product) => sum + product.stock_value, 0),
  );

  protected readonly lowCount = computed(() => this.active().filter((product) => product.is_low).length);

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.products().subscribe({
      next: (page) => {
        this.products.set(page.results);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(firstMessage(error, 'Impossible de charger le stock. Réessayez dans un instant.'));
        this.loading.set(false);
      },
    });
  }

  protected level(product: Product): number {
    return levelPercent(product.stock, product.low_stock_threshold);
  }
}
