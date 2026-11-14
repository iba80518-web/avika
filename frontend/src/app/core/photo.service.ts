import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, Injector, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_BASE } from './api.config';
import { Page } from './farming.models';
import { OutboxService, SubmitResult } from './outbox.service';
import { NewPhoto, Photo, PhotoKind } from './photo.models';

@Injectable({ providedIn: 'root' })
export class PhotoService {
  private readonly http = inject(HttpClient);
  private readonly injector = inject(Injector);

  list(filters: { cycle?: number; kind?: PhotoKind } = {}): Observable<Page<Photo>> {
    let params = new HttpParams();
    if (filters.cycle !== undefined) params = params.set('cycle', filters.cycle);
    if (filters.kind) params = params.set('kind', filters.kind);
    return this.http.get<Page<Photo>>(`${API_BASE}/photos/`, { params });
  }

  // Envoi en formulaire avec fichier. Aucun en-tête « Content-Type » à fixer : le navigateur
  // y ajoute lui-même la séparation des champs, indispensable au serveur.
  upload(body: NewPhoto): Observable<Photo> {
    const form = new FormData();
    form.append('cycle', String(body.cycle));
    form.append('kind', body.kind);
    form.append('taken_date', body.taken_date);
    form.append('uuid', body.uuid);
    if (body.note) form.append('note', body.note);
    if (body.egg_collection) form.append('egg_collection', String(body.egg_collection));
    if (body.flock_event) form.append('flock_event', String(body.flock_event));
    form.append('image', body.image, 'photo.jpg');
    return this.http.post<Photo>(`${API_BASE}/photos/`, form);
  }

  // Envoi par la file : sans réseau, la photo reste sur le téléphone. Le lien avec le ramassage
  // ou la mortalité se fait par leur uuid, connu du téléphone avant même l'envoi.
  submit(body: NewPhoto, label: string): Observable<SubmitResult<Photo>> {
    const fields: Record<string, string> = {
      cycle: String(body.cycle),
      kind: body.kind,
      taken_date: body.taken_date,
      uuid: body.uuid,
    };
    if (body.note) fields['note'] = body.note;
    if (body.egg_collection_uuid) fields['egg_collection_uuid'] = body.egg_collection_uuid;
    if (body.flock_event_uuid) fields['flock_event_uuid'] = body.flock_event_uuid;
    return this.injector
      .get(OutboxService)
      .submitPhoto<Photo>(label, `${API_BASE}/photos/`, fields, body.image, body.uuid);
  }

  // L'image est protégée : on la lit avec la connexion de l'utilisateur, sous forme de blob.
  file(photo: Photo): Observable<Blob> {
    return this.http.get(photo.file_url, { responseType: 'blob' });
  }
}
