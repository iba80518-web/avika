import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { firstMessage } from '../../core/api-errors';
import { localToday, shortDate } from '../../core/dates';
import { EggDay, EggSummary } from '../../core/egg.models';
import { EggService } from '../../core/egg.service';
import { Cycle } from '../../core/farming.models';
import { FarmingService } from '../../core/farming.service';
import { formatNumber } from '../../core/money';
import { newUuid } from '../../core/uuid';
import { PhotoCapture } from '../photo-capture/photo-capture';

const EGGS_PER_TRAY = 30;

// Nombre entier saisi par l'utilisateur (espaces tolérés) ; null si ce n'en est pas un.
function toInt(text: string): number | null {
  const clean = text.replace(/[\s\u00a0\u202f]/g, '');
  return /^\d+$/.test(clean) ? Number(clean) : null;
}

@Component({
  selector: 'app-eggs',
  imports: [RouterLink, PhotoCapture],
  templateUrl: './eggs.html',
  styleUrl: './eggs.scss',
})
export class Eggs {
  private readonly farming = inject(FarmingService);
  private readonly eggs = inject(EggService);

  protected readonly number = formatNumber;
  protected readonly shortDate = shortDate;
  protected readonly today = localToday();

  protected readonly cycles = signal<Cycle[]>([]);
  protected readonly cycleId = signal<number | null>(null);
  protected readonly summary = signal<EggSummary | null>(null);
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly date = signal(localToday());
  protected readonly collected = signal('');
  protected readonly broken = signal('');
  protected readonly note = signal('');
  protected readonly saving = signal(false);
  protected readonly formError = signal<string | null>(null);
  protected readonly saved = signal<string | null>(null);
  // Dernier ramassage enregistré : la photo s'y rattache.
  protected readonly lastCollectionId = signal<number | null>(null);
  protected readonly lastDate = signal(localToday());

  // Même identifiant tant que l'envoi n'a pas réussi : réessayer ne crée jamais de doublon.
  private uuid = newUuid();

  // Jours du plus récent au plus ancien.
  protected readonly days = computed<EggDay[]>(() =>
    [...(this.summary()?.days ?? [])].sort((a, b) => b.date.localeCompare(a.date)),
  );
  protected readonly lastDay = computed(() => this.days()[0] ?? null);
  protected readonly maxCollected = computed(() =>
    Math.max(1, ...this.days().map((day) => day.collected)),
  );
  protected readonly trays = computed(() =>
    Math.floor((this.summary()?.stock ?? 0) / EGGS_PER_TRAY),
  );

  // Œufs bons qui entreront en stock, calculés en direct pendant la saisie.
  protected readonly good = computed(() => {
    const collected = toInt(this.collected());
    const broken = this.broken().trim() === '' ? 0 : toInt(this.broken());
    return collected === null || broken === null ? null : collected - broken;
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.farming.cycles().subscribe({
      next: (page) => {
        const layers = page.results.filter(
          (cycle) => cycle.type === 'layer' && cycle.status === 'active',
        );
        this.cycles.set(layers);
        if (layers.length === 0) {
          this.loading.set(false);
          return;
        }
        this.cycleId.set(layers[0].id);
        this.loadSummary();
      },
      error: (error: unknown) => {
        this.loadError.set(firstMessage(error, 'Impossible de charger les bandes.'));
        this.loading.set(false);
      },
    });
  }

  private loadSummary(): void {
    const id = this.cycleId();
    if (id === null) return;
    this.eggs.summary(id).subscribe({
      next: (summary) => {
        this.summary.set(summary);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loadError.set(firstMessage(error, 'Impossible de charger les œufs.'));
        this.loading.set(false);
      },
    });
  }

  protected chooseCycle(event: Event): void {
    this.cycleId.set(Number(this.value(event)));
    this.lastCollectionId.set(null);
    this.summary.set(null);
    this.loadSummary();
  }

  protected barWidth(day: EggDay): number {
    return Math.round((day.collected / this.maxCollected()) * 100);
  }

  protected value(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  protected onSubmit(event: Event): void {
    event.preventDefault();
    if (this.saving()) return;
    this.formError.set(null);
    this.saved.set(null);

    const cycle = this.cycleId();
    const collected = toInt(this.collected());
    const broken = this.broken().trim() === '' ? 0 : toInt(this.broken());
    if (cycle === null) return;
    if (collected === null) {
      this.formError.set('Indiquez le nombre d’œufs ramassés (0 si aucun).');
      return;
    }
    if (broken === null) {
      this.formError.set('Les œufs cassés ou perdus doivent être un nombre entier.');
      return;
    }
    if (broken > collected) {
      this.formError.set('Il ne peut pas y avoir plus d’œufs cassés que d’œufs ramassés.');
      return;
    }
    if (!this.date() || this.date() > this.today) {
      this.formError.set('Choisissez une date qui n’est pas dans le futur.');
      return;
    }

    this.saving.set(true);
    this.eggs
      .create({
        cycle,
        collected_date: this.date(),
        collected,
        broken,
        note: this.note().trim(),
        uuid: this.uuid,
      })
      .subscribe({
        next: (collection) => {
          this.lastCollectionId.set(collection?.id ?? null);
          this.lastDate.set(this.date());
          this.saved.set(`Ramassage enregistré : ${formatNumber(collected - broken)} œufs en stock.`);
          this.collected.set('');
          this.broken.set('');
          this.note.set('');
          this.uuid = newUuid();
          this.saving.set(false);
          this.loadSummary();
        },
        error: (error: unknown) => {
          this.formError.set(firstMessage(error, 'Enregistrement impossible. Réessayez.'));
          this.saving.set(false);
        },
      });
  }
}
