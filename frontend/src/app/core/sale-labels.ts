import { Sale } from './finance.models';

const UNITS = {
  egg: ['œuf', 'œufs'],
  tray: ['plateau', 'plateaux'],
  crate: ['carton', 'cartons'],
} as const;

// Ce qui a été vendu, en mots : « 5 plateaux (150 œufs) », « 100 œufs » ou « 12 poulets ».
export function soldLabel(
  sale: Pick<Sale, 'quantity'> & Partial<Pick<Sale, 'product' | 'egg_unit' | 'egg_count'>>,
): string {
  if (sale.product === 'eggs' && sale.egg_unit) {
    const [one, many] = UNITS[sale.egg_unit];
    const unit = sale.quantity > 1 ? many : one;
    if (sale.egg_unit === 'egg') return `${sale.quantity} ${unit}`;
    return `${sale.quantity} ${unit} (${sale.egg_count ?? '?'} œufs)`;
  }
  return `${sale.quantity} poulet${sale.quantity > 1 ? 's' : ''}`;
}

// Tarif noté pour une vente d'œufs ; vide pour une vente de volailles.
export function tierLabel(sale: Partial<Pick<Sale, 'product' | 'price_tier'>>): string {
  if (sale.product !== 'eggs') return '';
  return sale.price_tier === 'wholesale' ? ' · tarif gros' : sale.price_tier === 'retail' ? ' · tarif détail' : '';
}
