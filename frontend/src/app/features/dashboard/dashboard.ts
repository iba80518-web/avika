import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';

import { DashboardData, Reminder } from '../../core/dashboard.models';
import { DashboardService } from '../../core/dashboard.service';
import { formatCompact, formatMoney, formatNumber } from '../../core/money';

interface Bar {
  label: string;
  value: number;
  tone: 'leaf' | 'yolk' | 'ink' | 'danger';
  height: number;
}

interface ReminderGroup {
  title: string;
  tone: 'danger' | 'warn' | 'ok';
  items: Reminder[];
}

const KIND_LABELS: Record<string, string> = {
  vaccine: 'Vaccin',
  medicine: 'Traitement',
};

const RING_RADIUS = 52;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

@Component({
  selector: 'app-dashboard',
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard {
  private readonly service = inject(DashboardService);

  protected readonly data = signal<DashboardData | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);

  protected readonly number = formatNumber;
  protected readonly money = formatMoney;
  protected readonly compact = formatCompact;
  protected readonly ringRadius = RING_RADIUS;
  protected readonly average = (value: number): string =>
    (Math.round(value * 10) / 10).toString().replace('.', ',');

  protected readonly today = computed(() => {
    const value = this.data()?.date;
    if (!value) return '';
    const text = new Date(`${value}T00:00:00`).toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    });
    return text.charAt(0).toUpperCase() + text.slice(1);
  });

  // Barres du mois : chaque hauteur est relative à la plus grande valeur.
  protected readonly bars = computed<Bar[]>(() => {
    const finance = this.data()?.finance;
    if (!finance) return [];
    const items: Omit<Bar, 'height'>[] = [
      { label: 'Ventes', value: finance.revenue_month, tone: 'leaf' },
      { label: 'Encaissé', value: finance.collected_month, tone: 'yolk' },
      { label: 'Dépenses', value: finance.expenses_month, tone: 'ink' },
      { label: 'À encaisser', value: finance.receivables_total, tone: 'danger' },
    ];
    const max = Math.max(...items.map((item) => item.value), 1);
    return items.map((item) => ({
      ...item,
      height: item.value > 0 ? Math.max((item.value / max) * 100, 4) : 0,
    }));
  });

  protected readonly collectionRate = computed(() => {
    const finance = this.data()?.finance;
    if (!finance || finance.revenue_month <= 0) return 0;
    return Math.min(Math.round((finance.collected_month / finance.revenue_month) * 100), 100);
  });

  protected readonly ringDash = computed(
    () => `${(this.collectionRate() / 100) * RING_LENGTH} ${RING_LENGTH}`,
  );

  protected readonly reminderGroups = computed<ReminderGroup[]>(() => {
    const reminders = this.data()?.health_reminders;
    if (!reminders) return [];
    return [
      { title: 'En retard', tone: 'danger' as const, items: reminders.overdue },
      { title: 'Aujourd’hui', tone: 'warn' as const, items: reminders.today },
      { title: 'Demain', tone: 'ok' as const, items: reminders.tomorrow },
    ].filter((group) => group.items.length > 0);
  });

  constructor() {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.load().subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.error.set(
          error instanceof HttpErrorResponse && error.status === 0
            ? 'Pas de connexion. Vos données affichées ne sont peut-être plus à jour.'
            : 'Impossible de charger le tableau de bord. Réessayez dans un instant.',
        );
        this.loading.set(false);
      },
    });
  }

  // Couleur d'avertissement visuelle seulement : les vraies alertes viennent du serveur.
  protected mortalityTone(rate: number): 'ok' | 'warn' | 'danger' {
    if (rate >= 8) return 'danger';
    if (rate >= 5) return 'warn';
    return 'ok';
  }

  protected kindLabel(kind: string): string {
    return KIND_LABELS[kind] ?? kind;
  }
}
