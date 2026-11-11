export type ProductType = 'feed' | 'vaccine' | 'medicine' | 'equipment' | 'packaging' | 'other';

export interface Product {
  id: number;
  name: string;
  product_type: ProductType;
  base_unit: string;
  low_stock_threshold: string;
  is_active: boolean;
  stock: string;
  stock_value: number;
  is_low: boolean;
  created_at: string;
}

export type MovementType = 'entry' | 'exit' | 'loss' | 'adjustment';

export interface StockMovement {
  id: number;
  uuid: string;
  movement_type: MovementType;
  base_quantity: string;
  total_cost: number;
  movement_date: string;
  cycle: number | null;
  note: string;
  created_by: number | null;
  created_at: string;
}

export interface NewProduct {
  name: string;
  product_type: ProductType;
  base_unit: string;
  low_stock_threshold: number;
}

// Entrée : total_cost obligatoire. Sortie : cycle facultatif (bande en cours), coût calculé par le serveur.
export interface NewMovement {
  movement_type: 'entry' | 'exit' | 'loss';
  quantity: number;
  movement_date: string;
  total_cost?: number;
  cycle?: number;
  note: string;
  uuid: string;
}
