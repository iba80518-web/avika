export interface EggCollection {
  id: number;
  uuid: string;
  cycle: number;
  cycle_name: string;
  collected_date: string;
  collected: number;
  // Dont cassés ou perdus : ils comptent dans « collected » mais pas dans le stock.
  broken: number;
  note: string;
  created_at: string;
}

export interface NewEggCollection {
  cycle: number;
  collected_date: string;
  collected: number;
  broken: number;
  note: string;
  uuid: string;
}

export interface EggCollectionChanges {
  collected: number;
  broken: number;
  note: string;
}

// Une journée de ponte ; « rate » est le taux de ponte en % (œufs ramassés / poules présentes).
export interface EggDay {
  date: string;
  collected: number;
  broken: number;
  hens: number;
  rate: number;
}

export interface EggSummary {
  cycle: number;
  // Œufs disponibles : ramassés - cassés - vendus.
  stock: number;
  days: EggDay[];
}
