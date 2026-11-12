import { Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth.service';

const ROLE_LABELS: Record<string, string> = {
  owner: 'Propriétaire',
  manager: 'Gérant',
  employee: 'Employé',
  accountant: 'Comptable',
  vet: 'Vétérinaire',
  observer: 'Observateur',
};

interface NavItem {
  permission?: string; // droit requis pour voir cet onglet
  label: string;
  icon: string;
  path: string | null; // null = écran pas encore construit
}

@Component({
  selector: 'app-shell',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  // Pour ajouter un écran : renseigner son `path` ici et déclarer la route dans app.routes.ts.
  protected readonly nav: NavItem[] = [
    { label: 'Accueil', icon: 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10', path: '/' },
    {
      label: 'Bandes',
      icon: 'M12 3c3.5 0 6.5 5.5 6.5 10a6.5 6.5 0 0 1-13 0C5.5 8.5 8.5 3 12 3z',
      path: '/bandes',
    },
    {
      label: 'Stock',
      icon: 'M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10',
      path: '/stock',
      permission: 'manage_feed',
    },
    {
      label: 'Ventes',
      icon: 'M5 19V9M11 19V5M17 19v-7',
      path: '/ventes',
      permission: 'manage_sales',
    },
    {
      label: 'Dépenses',
      icon: 'M12 3v18M16 7.5c0-1.9-1.8-3-4-3s-4 1.1-4 3 1.8 2.8 4 3.2 4 1.3 4 3.3-1.8 3-4 3-4-1.1-4-3',
      path: '/depenses',
      permission: 'manage_expenses',
    },
    { label: 'Santé', icon: 'M10 3h4v7h7v4h-7v7h-4v-7H3v-4h7z', path: null },
  ];

  protected readonly visibleNav = computed(() =>
    this.nav.filter((item) => !item.permission || this.auth.can(item.permission)),
  );

  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly organizationName = computed(
    () => this.auth.activeMembership()?.organization.name ?? '',
  );
  protected readonly roleLabel = computed(() => {
    const role = this.auth.activeMembership()?.role ?? '';
    return ROLE_LABELS[role] ?? role;
  });

  protected logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigateByUrl('/connexion'));
  }
}
