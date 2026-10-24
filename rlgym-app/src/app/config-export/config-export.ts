import { Component, ElementRef, OnInit, afterNextRender, inject, input, output, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ConfigExport, ConfigsService, ExportFormat } from '../api';

const FORMATS: { format: ExportFormat; label: string; hint: string }[] = [
  { format: ExportFormat.Snippet, label: 'Python snippet', hint: 'The imports and the RLGym(...) call, to paste into your code.' },
  { format: ExportFormat.Script, label: 'Runnable script', hint: 'Builds the env, resets it once and prints the agents and their observations.' },
  { format: ExportFormat.Json, label: 'JSON', hint: 'The config itself, to share or back up.' },
];

type Result =
  | { state: 'loading' }
  | { state: 'done'; export: ConfigExport }
  | { state: 'failed'; message: string };

// The export of a saved config: pick a format, preview it, copy it or save it to a file.
@Component({
  selector: 'app-config-export',
  templateUrl: './config-export.html',
  styleUrl: './config-export.css',
  host: { '(document:keydown.escape)': 'closed.emit()' },
})
export class ConfigExportDialog implements OnInit {
  private api = inject(ConfigsService);
  private host = inject<ElementRef<HTMLElement>>(ElementRef);

  configId = input.required<string>();
  closed = output<void>();

  protected formats = FORMATS;
  protected json = ExportFormat.Json;
  protected format = signal<ExportFormat>(ExportFormat.Snippet);
  protected result = signal<Result>({ state: 'loading' });
  protected status = signal<{ ok: boolean; text: string } | null>(null);

  constructor() {
    afterNextRender(() => this.host.nativeElement.querySelector<HTMLElement>('input[type=radio]:checked')?.focus());
  }

  ngOnInit() {
    this.load();
  }

  protected pick(format: ExportFormat) {
    this.format.set(format);
    this.load();
  }

  private async load() {
    const format = this.format();
    this.result.set({ state: 'loading' });
    this.status.set(null);
    try {
      const exported = await firstValueFrom(this.api.exportConfig({ configId: this.configId(), format }));
      if (this.format() === format) this.result.set({ state: 'done', export: exported });   // not switched meanwhile
    } catch (err) {
      const detail = err instanceof HttpErrorResponse && typeof err.error?.detail === 'string'
        ? err.error.detail
        : 'Could not reach the backend.';
      this.result.set({ state: 'failed', message: detail });
    }
  }

  protected async copy(exported: ConfigExport) {
    try {
      await navigator.clipboard.writeText(exported.content);
      this.status.set({ ok: true, text: 'Copied to the clipboard.' });
    } catch {
      this.status.set({ ok: false, text: 'Could not copy to the clipboard.' });
    }
  }

  protected async save(exported: ConfigExport) {
    const json = exported.format === ExportFormat.Json;
    const filters = [json ? { name: 'JSON', extensions: ['json'] } : { name: 'Python', extensions: ['py'] }];
    if (!window.rlgym) {
      // Plain browser (ng serve without Electron): a download is the closest thing to "save as".
      const url = URL.createObjectURL(new Blob([exported.content], { type: json ? 'application/json' : 'text/x-python' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: exported.filename });
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    try {
      const path = await window.rlgym.saveFile({
        title: 'Export config', defaultName: exported.filename, filters, content: exported.content,
      });
      if (path) this.status.set({ ok: true, text: `Saved to ${path}` });
    } catch {
      this.status.set({ ok: false, text: 'Could not write the file.' });
    }
  }

  protected slotList(slots: string[]): string {
    return slots.join(', ');
  }
}
