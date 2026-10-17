import { Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { DiscoverResult, DiscoveredComponent, DiscoveredComponentKindEnum, DiscoveryService } from '../api';

// In the order RLGym builds an env (same as the backend's KINDS).
const KINDS: { kind: DiscoveredComponentKindEnum; label: string }[] = [
  { kind: DiscoveredComponentKindEnum.TransitionEngine, label: 'Transition engines' },
  { kind: DiscoveredComponentKindEnum.StateMutator, label: 'State mutators' },
  { kind: DiscoveredComponentKindEnum.ObsBuilder, label: 'Observation builders' },
  { kind: DiscoveredComponentKindEnum.ActionParser, label: 'Action parsers' },
  { kind: DiscoveredComponentKindEnum.RewardFunction, label: 'Reward functions' },
  { kind: DiscoveredComponentKindEnum.DoneCondition, label: 'Done conditions' },
  { kind: DiscoveredComponentKindEnum.SharedInfoProvider, label: 'Shared info providers' },
];

type Scan =
  | { state: 'scanning' }
  | { state: 'done'; result: DiscoverResult }
  | { state: 'no-interpreter' }                          // 409: nothing selected in Settings
  | { state: 'failed'; message: string };               // worker failure or backend unreachable

@Component({
  selector: 'app-components-page',
  imports: [RouterLink],
  templateUrl: './components-page.html',
  styleUrl: './components-page.css',
})
export class ComponentsPage {
  private discovery = inject(DiscoveryService);

  protected scan = signal<Scan>({ state: 'scanning' });

  protected groups = computed(() => {
    const s = this.scan();
    if (s.state !== 'done') return [];
    return KINDS.map(({ kind, label }) => ({
      kind,
      label,
      components: s.result.components[kind] ?? [],
    }));
  });

  protected total = computed(() => this.groups().reduce((n, g) => n + g.components.length, 0));

  constructor() {
    this.rescan();
  }

  protected async rescan() {
    this.scan.set({ state: 'scanning' });
    try {
      const result = await firstValueFrom(this.discovery.discoverComponents({ discoverRequest: {} }));
      this.scan.set({ state: 'done', result });
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 409) {
        this.scan.set({ state: 'no-interpreter' });
      } else {
        const detail = err instanceof HttpErrorResponse && typeof err.error?.detail === 'string'
          ? err.error.detail
          : 'Could not reach the backend.';
        this.scan.set({ state: 'failed', message: detail });
      }
    }
  }

  // "foo(a, b=1)": the constructor at a glance, like Python would show it.
  protected signature(c: DiscoveredComponent): string {
    const params = c.params.map((p) => (p.required ? p.name : `${p.name}=${p.default}`));
    return `${c.name}(${params.join(', ')})`;
  }
}
