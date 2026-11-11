import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'connexion',
    title: 'Connexion — AVIKA',
    loadComponent: () => import('./features/login/login').then((module) => module.Login),
  },
  {
    // Tout ce qui est protégé vit dans le shell (menu + zone de contenu).
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./features/shell/shell').then((module) => module.Shell),
    children: [
      {
        path: '',
        pathMatch: 'full',
        title: 'Tableau de bord — AVIKA',
        loadComponent: () =>
          import('./features/dashboard/dashboard').then((module) => module.Dashboard),
      },
      {
        path: 'bandes',
        title: 'Bandes — AVIKA',
        loadComponent: () => import('./features/cycles/cycles').then((module) => module.Cycles),
      },
      {
        path: 'bandes/:id',
        title: 'Détail de la bande — AVIKA',
        loadComponent: () =>
          import('./features/cycle-detail/cycle-detail').then((module) => module.CycleDetail),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
