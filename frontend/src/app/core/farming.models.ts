export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type CycleStatus = 'planned' | 'active' | 'completed' | 'cancelled';

export interface Cycle {
  id: number;
  coop: number;
  name: string;
  type: string;
  start_date: string;
  end_date: string | null;
  initial_count: number;
  supplier_name: string;
  unit_price: number;
  currency: string;
  target: string;
  planned_sale_date: string | null;
  status: CycleStatus;
  current_count: number;
  created_at: string;
}

export interface Coop {
  id: number;
  farm: number;
  name: string;
  capacity: number;
  type: string;
  location: string;
  status: string;
  description: string;
}

export interface CycleSummary {
  initial_count: number;
  entries: number;
  transfers_in: number;
  mortality: number;
  sold: number;
  transfers_out: number;
  corrections: number;
  current_count: number;
  mortality_rate: number;
}

export type EventType =
  | 'entry'
  | 'mortality'
  | 'sale'
  | 'transfer_in'
  | 'transfer_out'
  | 'correction';

export interface FlockEvent {
  id: number;
  uuid: string;
  event_type: EventType;
  quantity: number;
  event_date: string;
  cause: string;
  note: string;
  created_by: number | null;
  created_at: string;
}

export interface NewMortality {
  event_type: 'mortality';
  quantity: number;
  event_date: string;
  cause: string;
  uuid: string;
}

export type CycleType = 'broiler' | 'layer' | 'other';

export interface Farm {
  id: number;
  name: string;
  location: string;
}

export interface NewCycle {
  coop: number;
  name: string;
  type: CycleType;
  start_date: string;
  initial_count: number;
  unit_price: number;
  supplier_name: string;
  target: string;
  planned_sale_date: string | null;
}

export interface NewCoop {
  farm: number;
  name: string;
  capacity: number;
  type: CycleType;
}
