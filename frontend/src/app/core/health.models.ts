export type HealthKind = 'vaccine' | 'treatment' | 'other';
export type HealthStatus = 'planned' | 'done' | 'cancelled';

export const HEALTH_KINDS: { value: HealthKind; label: string }[] = [
  { value: 'vaccine', label: 'Vaccin' },
  { value: 'treatment', label: 'Traitement' },
  { value: 'other', label: 'Autre' },
];

export function kindLabel(kind: string): string {
  return HEALTH_KINDS.find((item) => item.value === kind)?.label ?? kind;
}

export interface HealthTask {
  id: number;
  uuid: string;
  cycle: number;
  cycle_name: string;
  name: string;
  kind: HealthKind;
  due_date: string;
  status: HealthStatus;
  done_date: string | null;
  product: number | null;
  product_name: string | null;
  quantity: string | null;
  note: string;
  created_by: number | null;
  created_at: string;
}

// Rappels calculés par le serveur : tâches à faire, classées par urgence.
export interface Reminders {
  overdue: HealthTask[];
  today: HealthTask[];
  tomorrow: HealthTask[];
}

export interface HealthTemplate {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  items: unknown[];
  created_at: string;
}

export interface NewHealthTask {
  uuid: string;
  cycle: number;
  name: string;
  kind: HealthKind;
  due_date: string;
  product?: number;
  note: string;
}

// quantity + use_stock : retire la quantité du stock du produit lié à la tâche.
export interface CompleteTask {
  done_date: string;
  quantity?: number;
  use_stock: boolean;
}

export interface ScheduleRequest {
  cycle: number;
  template: number;
}
