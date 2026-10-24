import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { ConfigSummary, ConfigsService } from '../api';

const UNREACHABLE = 'Could not reach the backend.';

// The backend's message when it has one (409 duplicate name, 422 validation), else a generic one.
function messageOf(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return `Invalid name: ${detail[0].msg}`;
  }
  return UNREACHABLE;
}

@Component({
  selector: 'app-configs-page',
  imports: [DatePipe, RouterLink],
  templateUrl: './configs-page.html',
  styleUrl: './configs-page.css',
})
export class ConfigsPage {
  private api = inject(ConfigsService);
  private router = inject(Router);

  protected configs = signal<ConfigSummary[] | null>(null);  // null until loaded
  protected loadError = signal<string | null>(null);

  protected newName = signal('');
  protected creating = signal(false);
  protected createError = signal<string | null>(null);

  protected confirmingDelete = signal<string | null>(null);  // id awaiting confirmation
  protected deleteError = signal<string | null>(null);

  constructor() {
    this.load();
  }

  private async load() {
    try {
      this.configs.set(await firstValueFrom(this.api.listConfigs()));
      this.loadError.set(null);
    } catch {
      this.loadError.set(UNREACHABLE);
    }
  }

  protected onNameInput(event: Event) {
    this.newName.set((event.target as HTMLInputElement).value);
    this.createError.set(null);
  }

  protected async create(event: Event) {
    event.preventDefault();
    const name = this.newName().trim();
    if (!name) return;
    this.creating.set(true);
    try {
      const created = await firstValueFrom(this.api.createConfig({ configIn: { name } }));
      this.newName.set('');
      await this.router.navigate(['/configs', created.id]);   // a new config is empty: go fill it in
    } catch (err) {
      this.createError.set(messageOf(err));
    } finally {
      this.creating.set(false);
    }
  }

  protected async confirmDelete(id: string) {
    this.deleteError.set(null);
    try {
      await firstValueFrom(this.api.deleteConfig({ configId: id }));
    } catch (err) {
      // Already gone (e.g. deleted from another window): just refresh.
      if (!(err instanceof HttpErrorResponse && err.status === 404)) this.deleteError.set(messageOf(err));
    }
    this.confirmingDelete.set(null);
    await this.load();
  }
}
