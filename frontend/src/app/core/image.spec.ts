import { fitWithin } from './image';

describe('fitWithin', () => {
  it('réduit une photo large en gardant les proportions', () => {
    expect(fitWithin(4000, 3000, 1280)).toEqual({ width: 1280, height: 960 });
  });

  it('réduit une photo verticale', () => {
    expect(fitWithin(3000, 4000, 1280)).toEqual({ width: 960, height: 1280 });
  });

  it('n\'agrandit jamais une petite photo', () => {
    expect(fitWithin(800, 600, 1280)).toEqual({ width: 800, height: 600 });
  });

  it('laisse intacte une taille invalide', () => {
    expect(fitWithin(0, 0, 1280)).toEqual({ width: 0, height: 0 });
  });
});
