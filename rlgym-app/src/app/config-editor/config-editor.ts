import { Component, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import {
  ComponentChoice, ConfigSummarySlotsEnum as Slot, ConfigsService, DiscoverResult, DiscoveredComponent,
  DiscoveredComponentKindEnum as Kind, DiscoveryService, EnvConfig,
} from '../api';
import { ConfigExportDialog } from '../config-export/config-export';

const UNREACHABLE = 'Could not reach the backend.';

// The arguments of rlgym.api.RLGym(...) in order, with the kind of component each one takes
// (same as SLOT_KINDS and REQUIRED_SLOTS in the backend's configs.py).
const SLOTS: { slot: Slot; kind: Kind; label: string; required: boolean }[] = [
  { slot: Slot.TransitionEngine, kind: Kind.TransitionEngine, label: 'Transition engine', required: true },
  { slot: Slot.StateMutator, kind: Kind.StateMutator, label: 'State mutator', required: true },
  { slot: Slot.ObsBuilder, kind: Kind.ObsBuilder, label: 'Observation builder', required: true },
  { slot: Slot.ActionParser, kind: Kind.ActionParser, label: 'Action parser', required: true },
  { slot: Slot.RewardFn, kind: Kind.RewardFunction, label: 'Reward function', required: true },
  { slot: Slot.TerminationCond, kind: Kind.DoneCondition, label: 'Termination condition', required: false },
  { slot: Slot.TruncationCond, kind: Kind.DoneCondition, label: 'Truncation condition', required: false },
  { slot: Slot.SharedInfoProvider, kind: Kind.SharedInfoProvider, label: 'Shared info provider', required: false },
];

type Choices = Partial<Record<Slot, Required<ComponentChoice>>>;

type Load =
  | { state: 'loading' }
  | { state: 'loaded' }
  | { state: 'not-found' }
  | { state: 'failed' };

type Scan =
  | { state: 'scanning' }
  | { state: 'done'; result: DiscoverResult }
  | { state: 'no-interpreter' }                          // 409: nothing selected in Settings
  | { state: 'failed'; message: string };               // worker failure or backend unreachable

// One constructor argument as the form shows it. Components missing from the scan have no
// signature, so only their saved arguments are shown, untyped.
interface ParamField {
  name: string;
  type: string | null;
  default: string | null;
  required: boolean;
  value: string;
  missing: boolean;   // required and empty
}

// The backend's message when it has one (409 duplicate name, 422 validation), else a generic one.
function messageOf(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const detail = err.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return `Invalid config: ${detail[0].msg}`;
  }
  return UNREACHABLE;
}

function choicesOf(cfg: EnvConfig): Choices {
  const choices: Choices = {};
  for (const { slot } of SLOTS) {
    const c = cfg.components?.[slot];
    if (c) choices[slot] = { qualified_name: c.qualified_name, params: { ...c.params } };
  }
  return choices;
}

// Order-independent, so that typing a value and clearing it again doesn't count as a change.
function sameChoices(a: Choices, b: Choices): boolean {
  return SLOTS.every(({ slot }) => {
    const x = a[slot], y = b[slot];
    if (!x || !y) return x === y;
    const keys = Object.keys(x.params);
    return x.qualified_name === y.qualified_name
      && keys.length === Object.keys(y.params).length
      && keys.every((k) => x.params[k] === y.params[k]);
  });
}

@Component({
  selector: 'app-config-editor',
  imports: [RouterLink, ConfigExportDialog],
  templateUrl: './config-editor.html',
  styleUrl: './config-editor.css',
})
export class ConfigEditor {
  private api = inject(ConfigsService);
  private discovery = inject(DiscoveryService);
  protected id = inject(ActivatedRoute).snapshot.paramMap.get('id')!;

  protected load = signal<Load>({ state: 'loading' });
  protected scan = signal<Scan>({ state: 'scanning' });

  private saved = signal<EnvConfig | null>(null);
  protected name = signal('');
  protected choices = signal<Choices>({});

  protected saving = signal(false);
  protected saveError = signal<string | null>(null);
  protected justSaved = signal(false);

  protected exporting = signal(false);

  protected dirty = computed(() => {
    const saved = this.saved();
    return saved !== null
      && (this.name().trim() !== saved.name || !sameChoices(this.choices(), choicesOf(saved)));
  });

  protected slots = computed(() => {
    const s = this.scan();
    const choices = this.choices();
    return SLOTS.map((def) => {
      const options = s.state === 'done' ? s.result.components[def.kind] ?? [] : [];
      const choice = choices[def.slot];
      const component = choice ? options.find((c) => c.qualified_name === choice.qualified_name) ?? null : null;
      const params = choice ? this.fields(choice, component) : [];
      return { ...def, options, choice, component, params, missing: params.filter((p) => p.missing).length };
    });
  });

  // What still stands between this config and a buildable env.
  protected todo = computed(() => {
    const slots = this.slots();
    return {
      slots: slots.filter((s) => s.required && !s.choice).length,
      params: slots.reduce((n, s) => n + s.missing, 0),
    };
  });

  constructor() {
    this.fetch();
    this.rescan();
  }

  private async fetch() {
    try {
      this.reset(await firstValueFrom(this.api.getConfig({ configId: this.id })));
      this.load.set({ state: 'loaded' });
    } catch (err) {
      const notFound = err instanceof HttpErrorResponse && (err.status === 404 || err.status === 422);
      this.load.set({ state: notFound ? 'not-found' : 'failed' });
    }
  }

  private reset(cfg: EnvConfig) {
    this.saved.set(cfg);
    this.name.set(cfg.name);
    this.choices.set(choicesOf(cfg));
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
          : UNREACHABLE;
        this.scan.set({ state: 'failed', message: detail });
      }
    }
  }

  private fields(choice: Required<ComponentChoice>, component: DiscoveredComponent | null): ParamField[] {
    if (!component) {
      return Object.entries(choice.params).map(([name, value]) => (
        { name, type: null, default: null, required: false, value, missing: false }
      ));
    }
    return component.params.map((p) => {
      const value = choice.params[p.name] ?? '';
      return { ...p, value, missing: p.required && !value };
    });
  }

  private edited() {
    this.saveError.set(null);
    this.justSaved.set(false);
  }

  protected onNameInput(event: Event) {
    this.name.set((event.target as HTMLInputElement).value);
    this.edited();
  }

  // Another component takes other arguments, so the previous ones are dropped.
  protected choose(slot: Slot, event: Event) {
    const qualifiedName = (event.target as HTMLSelectElement).value;
    this.choices.update((choices) => {
      const next = { ...choices };
      if (qualifiedName) next[slot] = { qualified_name: qualifiedName, params: {} };
      else delete next[slot];
      return next;
    });
    this.edited();
  }

  // An empty value is left out, so the constructor's default applies.
  protected setParam(slot: Slot, param: string, event: Event) {
    const value = (event.target as HTMLInputElement).value.trim();
    this.choices.update((choices) => {
      const choice = choices[slot];
      if (!choice) return choices;
      const params = { ...choice.params };
      if (value) params[param] = value;
      else delete params[param];
      return { ...choices, [slot]: { ...choice, params } };
    });
    this.edited();
  }

  protected async save(event: Event) {
    event.preventDefault();
    const name = this.name().trim();
    if (!name || this.saving()) return;
    this.saving.set(true);
    try {
      this.reset(await firstValueFrom(this.api.updateConfig({
        configId: this.id,
        configIn: { name, components: this.choices() },
      })));
      this.saveError.set(null);
      this.justSaved.set(true);
    } catch (err) {
      this.saveError.set(
        err instanceof HttpErrorResponse && err.status === 404
          ? 'This config no longer exists; it was deleted from another window.'
          : messageOf(err),
      );
    } finally {
      this.saving.set(false);
    }
  }

  protected discard() {
    const saved = this.saved();
    if (saved) this.reset(saved);
    this.edited();
  }

  protected optionLabel(c: DiscoveredComponent): string {
    return `${c.name} (${c.module})`;
  }
}
