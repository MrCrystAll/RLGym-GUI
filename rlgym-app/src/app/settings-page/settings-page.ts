import { Component, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { DiscoveryService, PythonInfo, Settings, SettingsService } from '../api';

type Check =
  | { state: 'none' }                                    // no interpreter entered
  | { state: 'checking' }
  | { state: 'done'; info: PythonInfo }                  // info.error set if it can't be used
  | { state: 'unreachable' };                            // the backend didn't answer

const UNREACHABLE = 'Could not reach the backend.';

// One module per line in the textarea; blank lines ignored.
function parseModules(text: string): string[] {
  return text.split('\n').map((m) => m.trim()).filter(Boolean);
}

@Component({
  selector: 'app-settings-page',
  imports: [],
  templateUrl: './settings-page.html',
  styleUrl: './settings-page.css',
})
export class SettingsPage {
  private settingsApi = inject(SettingsService);
  private discovery = inject(DiscoveryService);

  // The file dialog only exists inside Electron (not in a plain browser on `ng serve`).
  protected readonly canBrowse = !!window.rlgym;

  protected loaded = signal(false);
  protected loadError = signal<string | null>(null);
  protected python = signal('');
  protected modulesText = signal('');
  private saved = signal<{ python: string; modules: string[] }>({ python: '', modules: [] });

  protected check = signal<Check>({ state: 'none' });
  private checkSeq = 0;

  protected saving = signal(false);
  protected saveError = signal<string | null>(null);
  protected justSaved = signal(false);

  protected modules = computed(() => parseModules(this.modulesText()));
  protected dirty = computed(() => {
    const saved = this.saved();
    const modules = this.modules();
    return this.python().trim() !== saved.python
      || modules.length !== saved.modules.length
      || modules.some((m, i) => m !== saved.modules[i]);
  });

  constructor() {
    this.load();
  }

  private async load() {
    try {
      this.apply(await firstValueFrom(this.settingsApi.getSettings()));
      this.loaded.set(true);
      await this.checkPython();
    } catch {
      this.loadError.set(UNREACHABLE);
    }
  }

  private apply(settings: Settings) {
    const python = settings.python ?? '';
    const modules = settings.modules ?? [];
    this.saved.set({ python, modules });
    this.python.set(python);
    this.modulesText.set(modules.join('\n'));
  }

  protected onPythonInput(event: Event) {
    this.python.set((event.target as HTMLInputElement).value);
    this.justSaved.set(false);
  }

  protected onModulesInput(event: Event) {
    this.modulesText.set((event.target as HTMLTextAreaElement).value);
    this.justSaved.set(false);
  }

  protected async browse() {
    const path = await window.rlgym?.openFile({
      title: 'Select a Python interpreter',
      filters: [
        { name: 'Python', extensions: ['exe'] },
        { name: 'All files', extensions: ['*'] },
      ],
    });
    if (path) {
      this.python.set(path);
      this.justSaved.set(false);
      await this.checkPython();
    }
  }

  protected async checkPython() {
    const python = this.python().trim();
    const seq = ++this.checkSeq;                         // ignore answers to older checks
    if (!python) {
      this.check.set({ state: 'none' });
      return;
    }
    this.check.set({ state: 'checking' });
    try {
      const info = await firstValueFrom(this.discovery.getPythonInfo({ python }));
      if (seq === this.checkSeq) this.check.set({ state: 'done', info });
    } catch {
      if (seq === this.checkSeq) this.check.set({ state: 'unreachable' });
    }
  }

  protected async save() {
    this.saving.set(true);
    this.saveError.set(null);
    try {
      const settings = await firstValueFrom(this.settingsApi.updateSettings({
        settings: { python: this.python().trim() || null, modules: this.modules() },
      }));
      this.apply(settings);                              // shows the cleaned-up values
      this.justSaved.set(true);
    } catch {
      this.saveError.set(UNREACHABLE);
    } finally {
      this.saving.set(false);
    }
  }
}
