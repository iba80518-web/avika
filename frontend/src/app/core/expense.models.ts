export type ExpenseCategory =
  | 'chicks'
  | 'labor'
  | 'transport'
  | 'utilities'
  | 'equipment'
  | 'rent'
  | 'other';

export const EXPENSE_CATEGORIES: { value: ExpenseCategory; label: string }[] = [
  { value: 'chicks', label: 'Poussins' },
  { value: 'labor', label: 'Main-d’œuvre' },
  { value: 'transport', label: 'Transport' },
  { value: 'utilities', label: 'Eau et électricité' },
  { value: 'equipment', label: 'Matériel' },
  { value: 'rent', label: 'Loyer' },
  { value: 'other', label: 'Autre' },
];

export function categoryLabel(category: string): string {
  return EXPENSE_CATEGORIES.find((item) => item.value === category)?.label ?? category;
}

export interface Expense {
  id: number;
  uuid: string;
  amount: number;
  expense_date: string;
  category: ExpenseCategory;
  description: string;
  supplier: number | null;
  cycle: number | null;
  created_by: number | null;
  created_at: string;
}

export interface NewExpense {
  uuid: string;
  amount: number;
  expense_date: string;
  category: ExpenseCategory;
  description: string;
  cycle?: number;
}

// Pour une correction : le fournisseur n'est pas touché, la bande peut être retirée (null).
export interface ExpenseChanges {
  amount: number;
  expense_date: string;
  category: ExpenseCategory;
  description: string;
  cycle: number | null;
}
