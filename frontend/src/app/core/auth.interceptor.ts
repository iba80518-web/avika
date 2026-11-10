import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { API_BASE } from './api.config';
import { AuthService } from './auth.service';

function isAuthEndpoint(url: string): boolean {
  return url.includes('/auth/login/') || url.includes('/auth/refresh/');
}

/**
 * Ajoute à chaque appel vers l'API le jeton d'accès (Authorization) et l'exploitation active
 * (X-Organization). Si le serveur répond 401 (jeton expiré), renouvelle le jeton une fois
 * et rejoue la requête ; si le renouvellement échoue, la session est fermée.
 */
export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!request.url.startsWith(API_BASE) || isAuthEndpoint(request.url)) {
    return next(request);
  }

  const withCredentials = (original: HttpRequest<unknown>, token: string | null) => {
    let headers = original.headers;
    if (token !== null) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    const organization = auth.activeOrganizationId();
    if (organization !== null) {
      headers = headers.set('X-Organization', String(organization));
    }
    return original.clone({ headers });
  };

  return next(withCredentials(request, auth.accessToken())).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && auth.hasRefreshToken()) {
        return auth.refreshAccess().pipe(
          switchMap((token) => next(withCredentials(request, token))),
          catchError((refreshError: unknown) => {
            auth.clearSession();
            void router.navigate(['/connexion']);
            return throwError(() => refreshError);
          }),
        );
      }
      return throwError(() => error);
    }),
  );
};
