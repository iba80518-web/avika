export type SaleType = 'count' | 'weight';
export type SaleStatus = 'active' | 'cancelled';
export type PaymentMethod = 'cash' | 'mobile_money' | 'bank_transfer' | 'other';

export interface Sale {
  id: number;
  uuid: string;
  customer: number | null;
  customer_name: string | null;
  cycle: number;
  sale_date: string;
  sale_type: SaleType;
  quantity: number;
  weight_kg: string | null;
  unit_price: number;
  total_amount: number;
  paid: number;
  balance: number;
  status: SaleStatus;
  note: string;
  created_by: number | null;
  created_at: string;
}

export interface SalePayment {
  id: number;
  uuid: string;
  sale: number;
  amount: number;
  payment_date: string;
  method: PaymentMethod;
  created_by: number | null;
  created_at: string;
}

export interface Customer {
  id: number;
  name: string;
  phone: string;
  address: string;
  customer_type: string;
  is_active: boolean;
  created_at: string;
}

// « Argent à recevoir » : ce que chaque client doit encore.
export interface Receivable {
  customer: number;
  customer_name: string;
  total_due: number;
  sales_count: number;
}

// Aucun total envoyé : le serveur le calcule. Sans client, la vente doit être payée en totalité.
export interface NewSale {
  uuid: string;
  cycle: number;
  customer?: number;
  sale_date: string;
  sale_type: SaleType;
  quantity: number;
  weight_kg?: number;
  unit_price: number;
  paid_amount: number;
  payment_method: PaymentMethod;
  note: string;
}

export interface NewPayment {
  uuid: string;
  amount: number;
  payment_date: string;
  method: PaymentMethod;
}
