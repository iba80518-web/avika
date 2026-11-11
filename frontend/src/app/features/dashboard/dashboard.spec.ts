import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DashboardData } from '../../core/dashboard.models';
import { Dashboard } from './dashboard';

const SAMPLE: DashboardData = {
  date: '2026-11-10',
  active_cycles: [
    {
      id: 2,
      name: 'Démo Bande B',
      coop: 'Poulailler B',
      start_date: '2026-10-29',
      day_number: 13,
      current_count: 450,
      mortality_rate: 10,
      birds_sold: 0,
    },
  ],
  birds_alive: 450,
  mortality_alerts: [],
  low_stock: [{ id: 1, name: 'Aliment démarrage', stock: '70.000', unit: 'kg', threshold: '100.000' }],
  finance: {
    month_start: '2026-11-01',
    revenue_month: 8_100_000,
    collected_month: 5_700_000,
    expenses_month: 1_150_000,
    receivables_total: 2_400_000,
  },
  health_reminders: {
    overdue: [
      { id: 1, name: 'Rappel vaccin', kind: 'vaccine', due_date: '2026-11-08', cycle_name: 'Démo Bande B' },
    ],
    today: [],
    tomorrow: [],
  },
};

describe('Dashboard', () => {
  let fixture: ComponentFixture<Dashboard>;
  let root: HTMLElement;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Dashboard],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Dashboard);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('affiche les chiffres, les bandes et les alertes reçus', async () => {
    http.expectOne('/api/v1/dashboard/').flush(SAMPLE);
    await fixture.whenStable();
    fixture.detectChanges();
    const text = root.textContent ?? '';
    expect(text).toContain('Démo Bande B');
    expect(text).toContain('8,1 M');
    expect(text).toContain('70%');
    expect(text).toContain('Aliment démarrage');
    expect(text).toContain('Rappel vaccin');
  });

  it('masque les chiffres financiers quand le serveur ne les envoie pas', async () => {
    http.expectOne('/api/v1/dashboard/').flush({ ...SAMPLE, finance: null });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.textContent).not.toContain('Ventes du mois');
    expect(root.textContent).toContain('Volailles vivantes');
  });

  it('propose de réessayer hors connexion', async () => {
    http.expectOne('/api/v1/dashboard/').error(new ProgressEvent('error'));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('connexion');
    expect(root.textContent).toContain('Réessayer');
  });
});
