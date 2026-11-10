import { Component, computed, inject } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

const ROLE_LABELS: Record<string, string> = {
  owner: 'Propriétaire',
  manager: 'Gérant',
  employee: 'Employé',
  accountant: 'Comptable',
  vet: 'Vétérinaire',
  observer: 'Observateur',
};

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class Home {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');
  protected readonly organizationName = computed(
    () => this.auth.activeMembership()?.organization.name ?? '',
  );
  protected readonly roleLabel = computed(() => {
    const role = this.auth.activeMembership()?.role ?? '';
    return ROLE_LABELS[role] ?? role;
  });
  protected readonly permissionCount = computed(
    () => this.auth.activeMembership()?.permissions.length ?? 0,
  );

  protected logout(): void {
    this.auth.logout().subscribe(() => void this.router.navigateByUrl('/connexion'));
  }
}
