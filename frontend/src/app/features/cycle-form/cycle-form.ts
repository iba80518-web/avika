import { Component, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { forkJoin, of, switchMap, tap } from 'rxjs';

import { fieldErrors, firstMessage } from '../../core/api-errors';
import { AuthService } from '../../core/auth.service';
import { localToday } from '../../core/dates';
import { Coop, CycleType, Farm } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { formatNumber } from '../../core/money';

@Component({
  selector: 'app-cycle-form',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './cycle-form.html',
  styleUrl: './cycle-form.scss',
})
export class CycleForm {
  private readonly service = inject(FarmingService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly formBuilder = inject(FormBuilder);

  protected readonly number = formatNumber;
  protected readonly types: { value: CycleType; label: string }[] = [
    { value: 'broiler', label: 'Poulets de chair' },
    { value: 'layer', label: 'Pondeuses' },
    { value: 'other', label: 'Autre' },
  ];

  protected readonly coops = signal<Coop[]>([]);
  private readonly farms = signal<Farm[]>([]);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly serverErrors = signal<Record<string, string>>({});

  protected readonly creatingCoop = signal(false);
  protected readonly coopSaving = signal(false);
  protected readonly coopError = signal<string | null>(null);

  protected readonly canCreateCoop = computed(() => this.auth.can('manage_coops'));

  protected readonly form = this.formBuilder.nonNullable.group({
    coop: this.formBuilder.control<number | null>(null, Validators.required),
    name: ['', Validators.required],
    type: this.formBuilder.nonNullable.control<CycleType>('broiler'),
    start_date: [localToday(), Validators.required],
    initial_count: this.formBuilder.control<number | null>(null, [
      Validators.required,
      Validators.min(1),
    ]),
    unit_price: this.formBuilder.control<number | null>(0, Validators.min(0)),
    planned_sale_date: [''],
    supplier_name: [''],
    target: [''],
  });

  protected readonly coopForm = this.formBuilder.group({
    name: this.formBuilder.nonNullable.control('', Validators.required),
    capacity: this.formBuilder.control<number | null>(null, [Validators.required, Validators.min(1)]),
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    forkJoin({ coops: this.service.coops(), farms: this.service.farms() }).subscribe({
      next: ({ coops, farms }) => {
        this.coops.set(coops.results);
        this.farms.set(farms.results);
        if (coops.results.length === 1) {
          this.form.controls.coop.setValue(coops.results[0].id);
        }
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(firstMessage(error, 'Impossible de charger les poulaillers.'));
        this.loading.set(false);
      },
    });
  }

  // Message sous un champ : refus du serveur en priorité, sinon champ vide ou invalide.
  protected fieldError(name: string): string | null {
    const server = this.serverErrors()[name];
    if (server) return server;
    const control = this.form.get(name);
    return control && control.touched && control.invalid ? 'Champ obligatoire ou invalide.' : null;
  }

  protected createCoopOnEnter(event: Event): void {
    event.preventDefault();
    this.createCoop();
  }

  protected createCoop(): void {
    if (this.coopSaving()) return;
    if (this.coopForm.invalid) {
      this.coopForm.markAllAsTouched();
      this.coopError.set('Indiquez le nom et la capacité du poulailler (au moins 1).');
      return;
    }
    const { name, capacity } = this.coopForm.getRawValue();
    this.coopSaving.set(true);
    this.coopError.set(null);

    // Une exploitation neuve n'a pas encore de ferme : on en crée une, une seule fois.
    const farm$ =
      this.farms().length > 0
        ? of(this.farms()[0])
        : this.service.createFarm({ name: 'Site principal' }).pipe(tap((farm) => this.farms.set([farm])));

    farm$
      .pipe(
        switchMap((farm) =>
          this.service.createCoop({
            farm: farm.id,
            name: name.trim(),
            capacity: capacity as number,
            type: this.form.controls.type.value,
          }),
        ),
      )
      .subscribe({
        next: (coop) => {
          this.coops.update((list) => [...list, coop]);
          this.form.controls.coop.setValue(coop.id);
          this.coopForm.reset();
          this.creatingCoop.set(false);
          this.coopSaving.set(false);
        },
        error: (error: unknown) => {
          this.coopError.set(firstMessage(error));
          this.coopSaving.set(false);
        },
      });
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
      .createCycle({
        coop: value.coop as number,
        name: value.name.trim(),
        type: value.type,
        start_date: value.start_date,
        initial_count: value.initial_count as number,
        unit_price: value.unit_price ?? 0,
        supplier_name: value.supplier_name.trim(),
        target: value.target.trim(),
        planned_sale_date: value.planned_sale_date || null,
      })
      .subscribe({
        next: (cycle) => void this.router.navigate(['/bandes', cycle.id]),
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
