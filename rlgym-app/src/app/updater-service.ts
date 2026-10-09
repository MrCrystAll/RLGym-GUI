import { Injectable, NgZone, inject, signal } from '@angular/core';
import type { UpdateState } from '../electron';

@Injectable({ providedIn: 'root' })
export class UpdaterService {
  private zone = inject(NgZone);
  readonly state = signal<UpdateState>({ status: 'idle' });

  constructor() {
    window.rlgym?.updater.onState((s) => this.zone.run(() => this.state.set(s)));
  }

  check() { return window.rlgym?.updater.check(); }
  download() { return window.rlgym?.updater.download(); }
  install() { return window.rlgym?.updater.install(); }
}