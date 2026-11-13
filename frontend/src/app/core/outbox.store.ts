import { Injectable } from '@angular/core';

export type OutboxStatus = 'pending' | 'rejected';

// Une saisie faite sans réseau, gardée en attendant de pouvoir l'envoyer.
export interface OutboxEntry {
  id?: number;
  uuid: string;
  url: string;
  body: unknown;
  label: string;
  organization: number | null;
  createdAt: string;
  status: OutboxStatus;
  error?: string;
}

const DB_NAME = 'avika-outbox';
const STORE = 'entries';

function wrap<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Boîte d'envoi sur le téléphone (IndexedDB) : elle survit à la fermeture de l'application.
 * Si le navigateur refuse IndexedDB (navigation privée…), on garde en mémoire seulement :
 * `persistent` vaut alors false et l'écran le signale.
 */
@Injectable({ providedIn: 'root' })
export class OutboxStore {
  persistent = typeof indexedDB !== 'undefined';

  private memory: OutboxEntry[] = [];
  private nextId = 1;
  private db: Promise<IDBDatabase> | null = null;

  forceMemory(): void {
    this.persistent = false;
  }

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        request.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return this.db;
  }

  async all(): Promise<OutboxEntry[]> {
    if (this.persistent) {
      try {
        const db = await this.open();
        return await wrap(db.transaction(STORE).objectStore(STORE).getAll());
      } catch {
        this.persistent = false;
      }
    }
    return [...this.memory];
  }

  async add(entry: OutboxEntry): Promise<OutboxEntry> {
    const fresh: OutboxEntry = { ...entry };
    delete fresh.id;
    if (this.persistent) {
      try {
        const db = await this.open();
        const key = await wrap(db.transaction(STORE, 'readwrite').objectStore(STORE).add(fresh));
        return { ...fresh, id: Number(key) };
      } catch {
        this.persistent = false;
      }
    }
    const saved = { ...fresh, id: this.nextId++ };
    this.memory.push(saved);
    return saved;
  }

  async update(entry: OutboxEntry): Promise<void> {
    if (this.persistent) {
      try {
        const db = await this.open();
        await wrap(db.transaction(STORE, 'readwrite').objectStore(STORE).put(entry));
        return;
      } catch {
        this.persistent = false;
      }
    }
    this.memory = this.memory.map((item) => (item.id === entry.id ? entry : item));
  }

  async remove(id: number): Promise<void> {
    if (this.persistent) {
      try {
        const db = await this.open();
        await wrap(db.transaction(STORE, 'readwrite').objectStore(STORE).delete(id));
        return;
      } catch {
        this.persistent = false;
      }
    }
    this.memory = this.memory.filter((item) => item.id !== id);
  }
}
