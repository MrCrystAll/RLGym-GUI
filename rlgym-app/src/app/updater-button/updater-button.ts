import { Component, computed, inject } from '@angular/core';
import { UpdaterService } from '../updater-service';

type Tone = 'neutral' | 'accent' | 'success' | 'danger';

// Full class names written out literally so Tailwind's scanner can see them.
const TONES: Record<Tone, string> = {
  neutral: 'text-slate-500 border-slate-300 hover:border-slate-500 dark:text-slate-400 dark:border-slate-600',
  accent:  'text-blue-600 border-blue-600 dark:text-blue-400 dark:border-blue-400',
  success: 'text-green-600 border-green-600 dark:text-green-400 dark:border-green-400',
  danger:  'text-red-600 border-red-600 dark:text-red-400 dark:border-red-400',
};

@Component({
  selector: 'app-updater-button',
  imports: [],
  templateUrl: './updater-button.html',
  styleUrl: './updater-button.css',
})
export class UpdaterButton {
  private updates = inject(UpdaterService);
  protected state = this.updates.state;

  protected view = computed(() => {
    const s = this.state();
    switch (s.status) {
      case 'checking':
        return { label: 'Checking…', title: 'Checking for updates', tone: 'neutral' as Tone, busy: true, classes: TONES.neutral };
      case 'up-to-date':
        return { label: 'Up to date', title: 'Click to check again', tone: 'success' as Tone, busy: false, classes: TONES.success };
      case 'available':
        return { label: `Update to v${s.version}`, title: 'Download this update', tone: 'accent' as Tone, busy: false, classes: TONES.accent };
      case 'downloading':
        return { label: `Downloading ${s.percent}%`, title: 'Downloading update', tone: 'accent' as Tone, busy: true, classes: TONES.accent };
      case 'ready':
        return { label: 'Restart to update', title: `v${s.version} is ready to install`, tone: 'accent' as Tone, busy: false, classes: TONES.accent };
      case 'error':
        return { label: 'Update failed · Retry', title: s.message, tone: 'danger' as Tone, busy: false, classes: TONES.danger };
      default:
        return { label: 'Check for updates', title: 'Check for updates', tone: 'neutral' as Tone, busy: false, classes: TONES.neutral };
    }
  });

  protected onClick() {
    switch (this.state().status) {
      case 'available': return this.updates.download();
      case 'ready':     return this.updates.install();
      default:          return this.updates.check();   // idle, up-to-date, error
    }
  }
}
