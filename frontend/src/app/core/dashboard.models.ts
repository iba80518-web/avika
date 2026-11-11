export interface ActiveCycle {
  id: number;
  name: string;
  coop: string;
  start_date: string;
  day_number: number;
  current_count: number;
  mortality_rate: number;
  birds_sold: number;
}

export interface LowStockItem {
  id: number;
  name: string;
  stock: string;
  unit: string;
  threshold: string;
}

export interface Reminder {
  id: number;
  name: string;
  kind: string;
  due_date: string;
  cycle_name: string;
}

// Absent si l'utilisateur n'a pas le droit de voir les finances.
export interface FinanceSummary {
  month_start: string;
  revenue_month: number;
  collected_month: number;
  expenses_month: number;
  receivables_total: number;
}

export interface DashboardData {
  date: string;
  active_cycles: ActiveCycle[];
  birds_alive: number;
  mortality_alerts: Record<string, unknown>[];
  low_stock: LowStockItem[];
  finance?: FinanceSummary | null;
  health_reminders?: {
    overdue: Reminder[];
    today: Reminder[];
    tomorrow: Reminder[];
  } | null;
}
