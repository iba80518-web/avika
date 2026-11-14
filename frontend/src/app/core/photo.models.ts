export type PhotoKind = 'mortality' | 'eggs';

export const PHOTO_KINDS: { value: PhotoKind; label: string }[] = [
  { value: 'mortality', label: 'Volailles mortes' },
  { value: 'eggs', label: 'Œufs ramassés' },
];

export interface Photo {
  id: number;
  uuid: string;
  cycle: number;
  cycle_name: string;
  kind: PhotoKind;
  taken_date: string;
  width: number;
  height: number;
  size_bytes: number;
  note: string;
  egg_collection: number | null;
  flock_event: number | null;
  // Adresse protégée de l'image : on la lit avec la connexion, jamais comme un lien public.
  file_url: string;
  created_at: string;
}

export interface NewPhoto {
  cycle: number;
  kind: PhotoKind;
  taken_date: string;
  image: Blob;
  uuid: string;
  note?: string;
  egg_collection?: number | null;
  flock_event?: number | null;
  // Lien par uuid : sert à l'envoi différé, quand l'identifiant serveur n'existe pas encore.
  egg_collection_uuid?: string | null;
  flock_event_uuid?: string | null;
}
