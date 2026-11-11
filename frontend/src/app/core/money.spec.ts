import { formatCompact, formatMoney } from './money';

describe('money', () => {
  it('formate un montant avec séparateurs et devise', () => {
    expect(formatMoney(8_100_000).replace(/\s/g, ' ')).toBe('8 100 000 GNF');
  });

  it('raccourcit les grands nombres', () => {
    expect(formatCompact(8_100_000)).toBe('8,1 M');
    expect(formatCompact(1_200_000_000)).toBe('1,2 Md');
    expect(formatCompact(250_000)).toBe('250 k');
    expect(formatCompact(950)).toBe('950');
  });
});
