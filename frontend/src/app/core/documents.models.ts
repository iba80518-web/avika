export type DocumentKind = 'invoice' | 'receipt';

export interface DocumentDefaults {
  name: string;
  address: string;
  phone: string;
  currency: string;
}

// Les paramètres de personnalisation des factures et reçus (un seul jeu par exploitation).
export interface DocumentSettings {
  business_name: string;
  address: string;
  phone: string;
  email: string;
  tax_id: string;
  registry_id: string;
  accent_color: string;
  footer_text: string;
  payment_terms: string;
  invoice_prefix: string;
  receipt_prefix: string;
  has_logo: boolean;
  logo_url: string | null;
  defaults: DocumentDefaults;
}

export type DocumentSettingsChanges = Partial<
  Omit<DocumentSettings, 'has_logo' | 'logo_url' | 'defaults'>
>;

export interface DocumentLine {
  label: string;
  quantity: string;
  unit: string;
  unit_price: number;
  total: number;
}

export interface DocumentIssuer {
  name: string;
  address: string;
  phone: string;
  email: string;
  tax_id: string;
  registry_id: string;
  logo_path: string;
  accent_color: string;
  footer_text: string;
  payment_terms: string;
}

// Copie figée à l'émission : ce que le client a reçu, quoi qu'il change ensuite dans les paramètres.
export interface DocumentContent {
  currency: string;
  issuer: DocumentIssuer;
  customer: { name: string; phone: string; address: string } | null;
  sale: {
    id: number;
    date: string;
    cycle: string;
    lines: DocumentLine[];
    total: number;
    note: string;
  };
  payment?: { id: number; amount: number; date: string; method: string };
  paid: number;
  balance: number;
}

export interface IssuedDocument {
  id: number;
  uuid: string;
  kind: DocumentKind;
  number: string;
  year: number;
  sequence: number;
  sale: number;
  payment: number | null;
  issued_on: string;
  customer_name: string;
  sale_status: 'active' | 'cancelled';
  content: DocumentContent;
  pdf_url: string;
  created_by: number | null;
  created_at: string;
}

export interface NewDocument {
  kind: DocumentKind;
  sale?: number;
  payment?: number;
  // Seulement utile pour un client de passage : le client enregistré prime côté serveur.
  customer_name?: string;
}
