import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from './auth.service';

/** Protège un écran : sans session (même après rechargement), on renvoie vers la connexion. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.restoreSession().pipe(map((open) => (open ? true : router.createUrlTree(['/connexion']))));
};

/** Protège un écran par un droit précis (ex. permissionGuard('view_finances')). */
export const permissionGuard =
  (permission: string): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    return auth.can(permission) ? true : router.createUrlTree(['/']);
  };
