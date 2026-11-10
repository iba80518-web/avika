import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'connexion',
    title: 'Connexion — AVIKA',
    loadComponent: () => import('./features/login/login').then((module) => module.Login),
  },
  {
    path: '',
    pathMatch: 'full',
    title: 'Accueil — AVIKA',
    canActivate: [authGuard],
    loadComponent: () => import('./features/home/home').then((module) => module.Home),
  },
  { path: '**', redirectTo: '' },
];
