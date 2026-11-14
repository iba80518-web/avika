import { Component, DestroyRef, computed, inject, input, output, signal } from '@angular/core';

import { firstMessage } from '../../core/api-errors';
import { AuthService } from '../../core/auth.service';
import { compressImage } from '../../core/image';
import { Photo, PhotoKind } from '../../core/photo.models';
import { PhotoService } from '../../core/photo.service';
import { newUuid } from '../../core/uuid';

@Component({
  selector: 'app-photo-capture',
  templateUrl: './photo-capture.html',
  styleUrl: './photo-capture.scss',
})
export class PhotoCapture {
  readonly cycle = input.required<number>();
  readonly kind = input.required<PhotoKind>();
  readonly date = input.required<string>();
  // Pour relier la photo à un ramassage d'œufs ou à une mortalité qui vient d'être enregistré.
  readonly eggCollection = input<number | null>(null);
  readonly flockEvent = input<number | null>(null);
  readonly uploaded = output<Photo>();

  private readonly photos = inject(PhotoService);
  private readonly auth = inject(AuthService);

  // Seuls les rôles autorisés à envoyer des photos voient ce bouton.
  protected readonly allowed = computed(() => this.auth.can('add_photos'));
  protected readonly title = computed(() =>
    this.kind() === 'eggs' ? 'Photo des œufs ramassés' : 'Photo des volailles mortes',
  );

  protected readonly blob = signal<Blob | null>(null);
  protected readonly previewUrl = signal<string | null>(null);
  protected readonly preparing = signal(false);
  protected readonly sending = signal(false);
  protected readonly done = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly sizeKb = computed(() => Math.max(1, Math.round((this.blob()?.size ?? 0) / 1024)));

  // Même identifiant tant que l'envoi n'a pas réussi : réessayer ne crée pas de doublon.
  private uuid = newUuid();

  constructor() {
    inject(DestroyRef).onDestroy(() => this.releasePreview());
  }

  private releasePreview(): void {
    const url = this.previewUrl();
    if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url);
    this.previewUrl.set(null);
  }

  protected async onFile(event: Event): Promise<void> {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.error.set(null);
    this.done.set(false);
    this.preparing.set(true);
    const reduced = await compressImage(file);
    this.releasePreview();
    this.blob.set(reduced);
    if (typeof URL.createObjectURL === 'function') {
      this.previewUrl.set(URL.createObjectURL(reduced));
    }
    this.preparing.set(false);
  }

  protected send(): void {
    const image = this.blob();
    if (!image || this.sending()) return;
    this.sending.set(true);
    this.error.set(null);
    this.photos
      .upload({
        cycle: this.cycle(),
        kind: this.kind(),
        taken_date: this.date(),
        image,
        uuid: this.uuid,
        egg_collection: this.eggCollection(),
        flock_event: this.flockEvent(),
      })
      .subscribe({
        next: (photo) => {
          this.done.set(true);
          this.blob.set(null);
          this.releasePreview();
          this.uuid = newUuid();
          this.sending.set(false);
          this.uploaded.emit(photo);
        },
        error: (error: unknown) => {
          this.error.set(firstMessage(error, 'Envoi impossible. Réessayez.'));
          this.sending.set(false);
        },
      });
  }
}
