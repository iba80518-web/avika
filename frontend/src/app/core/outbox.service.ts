import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { catchError, firstValueFrom, from, map, Observable, throwError } from 'rxjs';

import { firstMessage } from './api-errors';
import { AuthService } from './auth.service';
import { OutboxEntry, OutboxStore } from './outbox.store';

// Soit le serveur a répondu (queued: false), soit la saisie est gardée pour plus tard (queued: true).
export type SubmitResult<T> = { queued: false; result: T } | { queued: true };

const RETRY_EVERY_MS = 30_000;

function isNetworkError(error: unknown): boolean {
  return error instanceof HttpErrorResponse && error.status === 0;
}

// Refus définitif du serveur : inutile de renvoyer la même chose (sauf jeton expiré, délai, trop de demandes).
function isRejection(error: unknown): boolean {
  return (
    error instanceof HttpErrorResponse &&
    error.status >= 400 &&
    error.status < 500 &&
    ![401, 408, 429].includes(error.status)
  );
}

@Injectable({ providedIn: 'root' })
export class OutboxService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly store = inject(OutboxStore);
  private started = false;

  readonly online = signal(typeof navigator === 'undefined' ? true : navigator.onLine);
  readonly entries = signal<OutboxEntry[]>([]);
  readonly syncing = signal(false);

  get persistent(): boolean {
    return this.store.persistent;
  }

  // Seules les saisies de l'exploitation active sont montrées et envoyées : l'en-tête X-Organization est celui d'aujourd'hui.
  private forActive(): OutboxEntry[] {
    const organization = this.auth.activeOrganizationId();
    return this.entries().filter((entry) => entry.organization === organization);
  }

  pending(): OutboxEntry[] {
    return this.forActive().filter((entry) => entry.status === 'pending');
  }

  rejected(): OutboxEntry[] {
    return this.forActive().filter((entry) => entry.status === 'rejected');
  }

  /** À appeler une fois au démarrage : relit la boîte, écoute le réseau, réessaie régulièrement. */
  start(): void {
    if (this.started || typeof window === 'undefined') return;
    this.started = true;
    window.addEventListener('online', () => {
      this.online.set(true);
      void this.flush();
    });
    window.addEventListener('offline', () => this.online.set(false));
    window.setInterval(() => void this.flush(), RETRY_EVERY_MS);
    void this.store.all().then((list) => {
      this.entries.update((current) => {
        const known = new Set(current.map((entry) => entry.id));
        return [...list.filter((entry) => !known.has(entry.id)), ...current];
      });
      return this.flush();
    });
  }

  /** Envoie la saisie ; sans réseau, la garde et le dit. Une erreur du serveur remonte à l'écran. */
  submit<T>(label: string, url: string, body: unknown, uuid: string): Observable<SubmitResult<T>> {
    const queue = () =>
      from(this.enqueue(label, url, body, uuid)).pipe(map((): SubmitResult<T> => ({ queued: true })));
    if (!this.online()) return queue();
    return this.http.post<T>(url, body).pipe(
      map((result): SubmitResult<T> => ({ queued: false, result })),
      catchError((error: unknown) => (isNetworkError(error) ? queue() : throwError(() => error))),
    );
  }

  private async enqueue(label: string, url: string, body: unknown, uuid: string): Promise<void> {
    if (this.entries().some((entry) => entry.uuid === uuid && entry.url === url)) return;
    const saved = await this.store.add({
      uuid,
      url,
      body,
      label,
      organization: this.auth.activeOrganizationId(),
      createdAt: new Date().toISOString(),
      status: 'pending',
    });
    this.entries.update((list) => [...list, saved]);
  }

  /** Envoie les saisies en attente, une par une, dans l'ordre. S'arrête dès que le réseau lâche. */
  async flush(): Promise<void> {
    if (this.syncing() || !this.online() || this.auth.activeOrganizationId() === null) return;
    this.syncing.set(true);
    try {
      for (const entry of this.pending()) {
        if ((await this.send(entry)) === 'stop') break;
      }
    } finally {
      this.syncing.set(false);
    }
  }

  private async send(entry: OutboxEntry): Promise<'next' | 'stop'> {
    try {
      await firstValueFrom(this.http.post(entry.url, entry.body));
      await this.drop(entry.id);
      return 'next';
    } catch (error) {
      if (isRejection(error)) {
        const rejected: OutboxEntry = {
          ...entry,
          status: 'rejected',
          error: firstMessage(error, 'Refusée par le serveur.'),
        };
        await this.store.update(rejected);
        this.entries.update((list) => list.map((item) => (item.id === entry.id ? rejected : item)));
        return 'next';
      }
      return 'stop';
    }
  }

  private async drop(id: number | undefined): Promise<void> {
    if (id === undefined) return;
    await this.store.remove(id);
    this.entries.update((list) => list.filter((item) => item.id !== id));
  }

  /** Supprime une saisie refusée dont l'éleveur ne veut plus. */
  async dismiss(id: number | undefined): Promise<void> {
    await this.drop(id);
  }

  /** Remet une saisie refusée en attente (par exemple après avoir corrigé la cause) et réessaie. */
  async retry(id: number | undefined): Promise<void> {
    const entry = this.entries().find((item) => item.id === id);
    if (!entry) return;
    const again: OutboxEntry = { ...entry, status: 'pending' };
    delete again.error;
    await this.store.update(again);
    this.entries.update((list) => list.map((item) => (item.id === id ? again : item)));
    await this.flush();
  }
}
