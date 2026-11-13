import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { SyncStatus } from './features/sync-status/sync-status';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, SyncStatus],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
