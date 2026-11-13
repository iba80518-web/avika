import { Component, inject, signal } from '@angular/core';

import { shortDate } from '../../core/dates';
import { OutboxEntry } from '../../core/outbox.store';
import { OutboxService } from '../../core/outbox.service';

@Component({
  selector: 'app-sync-status',
  templateUrl: './sync-status.html',
  styleUrl: './sync-status.scss',
})
export class SyncStatus {
  protected readonly outbox = inject(OutboxService);
  protected readonly open = signal(false);
  protected readonly shortDate = shortDate;

  constructor() {
    this.outbox.start();
  }

  protected visible(): boolean {
    return (
      !this.outbox.online() ||
      this.outbox.syncing() ||
      this.outbox.pending().length > 0 ||
      this.outbox.rejected().length > 0
    );
  }

  protected tone(): 'off' | 'warn' | 'info' {
    if (!this.outbox.online()) return 'off';
    if (this.outbox.rejected().length > 0 && this.outbox.pending().length === 0) return 'warn';
    return 'info';
  }

  protected label(): string {
    const pending = this.outbox.pending().length;
    const rejected = this.outbox.rejected().length;
    const plural = (count: number) => (count > 1 ? 's' : '');
    if (!this.outbox.online()) {
      return pending > 0
        ? `Hors connexion · ${pending} saisie${plural(pending)} en attente`
        : 'Hors connexion';
    }
    if (this.outbox.syncing()) return 'Envoi en cours…';
    if (pending > 0) return `${pending} saisie${plural(pending)} en attente`;
    return `${rejected} saisie${plural(rejected)} refusée${plural(rejected)}`;
  }

  protected items(): OutboxEntry[] {
    return [...this.outbox.pending(), ...this.outbox.rejected()].sort(
      (a, b) => (a.id ?? 0) - (b.id ?? 0),
    );
  }

  protected sendNow(): void {
    void this.outbox.flush();
  }
}
