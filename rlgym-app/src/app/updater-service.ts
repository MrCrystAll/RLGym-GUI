import { Injectable, NgZone, inject, signal } from '@angular/core';
import type { ReleaseInfo, UpdateState } from '../electron';

@Injectable({ providedIn: 'root' })
export class UpdaterService {
  private zone = inject(NgZone);
  readonly state = signal<UpdateState>({ status: 'idle' });
  // The update on offer. Kept while it downloads, so its notes stay readable.
  readonly release = signal<ReleaseInfo | null>(null);

  constructor() {
    window.rlgym?.updater.onState((s) => this.zone.run(() => this.apply(s)));
  }

  check() { return window.rlgym?.updater.check(); }
  download() { return window.rlgym?.updater.download(); }
  install() { return window.rlgym?.updater.install(); }

  private apply(s: UpdateState) {
    this.state.set(s);
    if (s.status === 'available' || s.status === 'ready') {
      this.release.set({ version: s.version, notes: s.notes, date: s.date });
    } else if (s.status === 'up-to-date') {
      this.release.set(null);
    }
  }
}
