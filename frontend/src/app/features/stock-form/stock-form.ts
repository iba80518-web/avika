import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { fieldErrors, firstMessage } from '../../core/api-errors';
import { InventoryService } from '../../core/inventory.service';
import { ProductType } from '../../core/inventory.models';

@Component({
  selector: 'app-stock-form',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './stock-form.html',
  styleUrl: './stock-form.scss',
})
export class StockForm {
  private readonly service = inject(InventoryService);
  private readonly router = inject(Router);
  private readonly formBuilder = inject(FormBuilder);

  protected readonly types: { value: ProductType; label: string }[] = [
    { value: 'feed', label: 'Aliment' },
    { value: 'vaccine', label: 'Vaccin' },
    { value: 'medicine', label: 'Médicament' },
    { value: 'equipment', label: 'Équipement' },
    { value: 'packaging', label: 'Emballage' },
    { value: 'other', label: 'Autre' },
  ];
  protected readonly units = ['kg', 'g', 'litre', 'dose', 'flacon', 'sac', 'unité'];

  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly serverErrors = signal<Record<string, string>>({});

  protected readonly form = this.formBuilder.nonNullable.group({
    name: ['', Validators.required],
    product_type: this.formBuilder.nonNullable.control<ProductType>('feed'),
    base_unit: ['kg', Validators.required],
    low_stock_threshold: this.formBuilder.control<number | null>(0, [
      Validators.required,
      Validators.min(0),
    ]),
  });

  protected fieldError(name: string): string | null {
    const server = this.serverErrors()[name];
    if (server) return server;
    const control = this.form.get(name);
    return control && control.touched && control.invalid ? 'Champ obligatoire ou invalide.' : null;
  }

  protected submit(): void {
    if (this.saving()) return;
    this.serverErrors.set({});
    this.formError.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.formError.set('Complétez les champs signalés.');
      return;
    }
    const value = this.form.getRawValue();
    this.saving.set(true);
    this.service
      .createProduct({
        name: value.name.trim(),
        product_type: value.product_type,
        base_unit: value.base_unit.trim(),
        low_stock_threshold: value.low_stock_threshold ?? 0,
      })
      .subscribe({
        next: (product) => void this.router.navigate(['/stock', product.id]),
        error: (error: unknown) => {
          const errors = fieldErrors(error);
          this.serverErrors.set(errors);
          this.formError.set(
            Object.keys(errors).some((key) => key in this.form.controls)
              ? 'Corrigez les champs signalés.'
              : firstMessage(error),
          );
          this.saving.set(false);
        },
      });
  }
}
