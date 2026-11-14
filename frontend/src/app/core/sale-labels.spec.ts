import { soldLabel, tierLabel } from './sale-labels';

describe('soldLabel', () => {
  it('garde l\'affichage des volailles', () => {
    expect(soldLabel({ quantity: 1 })).toBe('1 poulet');
    expect(soldLabel({ quantity: 12, product: 'birds' })).toBe('12 poulets');
  });

  it('décrit une vente au plateau avec le nombre d\'œufs', () => {
    expect(soldLabel({ quantity: 5, product: 'eggs', egg_unit: 'tray', egg_count: 150 })).toBe(
      '5 plateaux (150 œufs)',
    );
    expect(soldLabel({ quantity: 1, product: 'eggs', egg_unit: 'tray', egg_count: 30 })).toBe(
      '1 plateau (30 œufs)',
    );
  });

  it('décrit un carton et une vente à l\'unité', () => {
    expect(soldLabel({ quantity: 1, product: 'eggs', egg_unit: 'crate', egg_count: 360 })).toBe(
      '1 carton (360 œufs)',
    );
    expect(soldLabel({ quantity: 100, product: 'eggs', egg_unit: 'egg', egg_count: 100 })).toBe(
      '100 œufs',
    );
  });

  it('indique le tarif seulement pour les œufs', () => {
    expect(tierLabel({ product: 'eggs', price_tier: 'wholesale' })).toBe(' · tarif gros');
    expect(tierLabel({ product: 'eggs', price_tier: 'retail' })).toBe(' · tarif détail');
    expect(tierLabel({ product: 'birds' })).toBe('');
  });
});
