import { Routes } from '@angular/router';

import { authGuard, permissionGuard } from './core/auth.guard';

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
        path: 'bandes/nouvelle',
        title: 'Nouvelle bande — AVIKA',
        loadComponent: () =>
          import('./features/cycle-form/cycle-form').then((module) => module.CycleForm),
      },
      {
        path: 'bandes/:id',
        title: 'Détail de la bande — AVIKA',
        loadComponent: () =>
          import('./features/cycle-detail/cycle-detail').then((module) => module.CycleDetail),
      },
      {
        path: 'stock',
        title: 'Stock — AVIKA',
        canActivate: [permissionGuard('manage_feed')],
        loadComponent: () => import('./features/stock/stock').then((module) => module.Stock),
      },
      {
        path: 'stock/nouveau',
        title: 'Nouveau produit — AVIKA',
        canActivate: [permissionGuard('manage_feed')],
        loadComponent: () =>
          import('./features/stock-form/stock-form').then((module) => module.StockForm),
      },
      {
        path: 'stock/:id',
        title: 'Produit — AVIKA',
        canActivate: [permissionGuard('manage_feed')],
        loadComponent: () =>
          import('./features/stock-detail/stock-detail').then((module) => module.StockDetail),
      },
      {
        path: 'ventes',
        title: 'Ventes — AVIKA',
        canActivate: [permissionGuard('manage_sales')],
        loadComponent: () => import('./features/sales/sales').then((module) => module.Sales),
      },
      {
        path: 'ventes/nouvelle',
        title: 'Nouvelle vente — AVIKA',
        canActivate: [permissionGuard('manage_sales')],
        loadComponent: () =>
          import('./features/sale-form/sale-form').then((module) => module.SaleForm),
      },
      {
        path: 'ventes/:id',
        title: 'Vente — AVIKA',
        canActivate: [permissionGuard('manage_sales')],
        loadComponent: () =>
          import('./features/sale-detail/sale-detail').then((module) => module.SaleDetail),
      },
      {
        path: 'depenses',
        title: 'Dépenses — AVIKA',
        canActivate: [permissionGuard('manage_expenses')],
        loadComponent: () =>
          import('./features/expenses/expenses').then((module) => module.Expenses),
      },
      {
        path: 'depenses/nouvelle',
        title: 'Nouvelle dépense — AVIKA',
        canActivate: [permissionGuard('manage_expenses')],
        loadComponent: () =>
          import('./features/expense-form/expense-form').then((module) => module.ExpenseForm),
      },
      {
        path: 'depenses/:id',
        title: 'Dépense — AVIKA',
        canActivate: [permissionGuard('manage_expenses')],
        loadComponent: () =>
          import('./features/expense-form/expense-form').then((module) => module.ExpenseForm),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
