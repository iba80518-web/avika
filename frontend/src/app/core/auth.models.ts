/** Jetons renvoyés par /auth/login/ et /auth/refresh/ (avec la rotation, refresh est renouvelé). */
export interface Tokens {
  access: string;
  refresh: string;
}

export interface UserProfile {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
}

export interface Organization {
  id: number;
  name: string;
  reference_currency: string;
}

/** Appartenance de l'utilisateur à une exploitation : son rôle et la liste exacte de ses droits. */
export interface Membership {
  organization: Organization;
  role: string;
  permissions: string[];
}

/** Réponse de /auth/me/. */
export interface MeResponse {
  user: UserProfile;
  memberships: Membership[];
}
