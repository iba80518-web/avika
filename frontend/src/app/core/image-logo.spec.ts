import { compressLogo } from './image';

describe('compressLogo', () => {
  it('renvoie l’original quand le navigateur ne sait pas réduire l’image', async () => {
    const file = new Blob(['pas une vraie image'], { type: 'image/png' });
    expect(await compressLogo(file)).toBe(file);
  });
});
