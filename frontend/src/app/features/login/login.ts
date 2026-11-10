import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly formBuilder = inject(FormBuilder);

  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly showPassword = signal(false);

  protected readonly form = this.formBuilder.nonNullable.group({
    identifier: ['', [Validators.required]],
    password: ['', [Validators.required]],
  });

  protected submit(): void {
    if (this.loading()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      this.error.set('Saisissez votre e-mail ou téléphone, puis votre mot de passe.');
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    const { identifier, password } = this.form.getRawValue();
    this.auth.login(identifier.trim(), password).subscribe({
      next: () => void this.router.navigateByUrl('/'),
      error: (error: unknown) => {
        this.error.set(this.messageFor(error));
        this.loading.set(false);
      },
    });
  }

  // Un seul message pour « inconnu » et « mauvais mot de passe » : on ne révèle pas quels comptes existent.
  private messageFor(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) {
        return 'Identifiant ou mot de passe incorrect. Vérifiez et réessayez.';
      }
      if (error.status === 429) {
        return 'Trop de tentatives. Patientez quelques minutes avant de réessayer.';
      }
      if (error.status === 0) {
        return 'Impossible de joindre le serveur. Vérifiez votre connexion.';
      }
    }
    return 'La connexion a échoué. Réessayez dans un instant.';
  }
}
