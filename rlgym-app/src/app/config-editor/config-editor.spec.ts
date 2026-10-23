import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';

import { ConfigEditor } from './config-editor';
import {
  ConfigsService, DiscoverResult, DiscoveredComponentKindEnum as Kind, DiscoveryService, EnvConfig,
} from '../api';

const ID = 'a'.repeat(32);

function result(partial: Partial<DiscoverResult['components']>): DiscoverResult {
  const components: DiscoverResult['components'] = {};
  for (const kind of Object.values(Kind)) components[kind] = partial[kind] ?? [];
  return { components, errors: [] };
}

function config(components: EnvConfig['components'] = {}, name = 'Kickoff'): EnvConfig {
  return { id: ID, name, components, created_at: '2026-10-20T10:00:00Z', updated_at: '2026-10-20T10:00:00Z' };
}

const GOAL_REWARD = {
  kind: Kind.RewardFunction,
  name: 'GoalReward',
  module: 'my_bot.rewards',
  qualified_name: 'my_bot.rewards.GoalReward',
  doc: '+weight when the given team scores.',
  params: [
    { name: 'weight', type: 'float', default: '1.0', required: false },
    { name: 'team', type: 'int', default: null, required: true },
  ],
};
const TOUCH_REWARD = {
  kind: Kind.RewardFunction,
  name: 'TouchReward',
  module: 'my_bot.rewards',
  qualified_name: 'my_bot.rewards.TouchReward',
  doc: null,
  params: [],
};

describe('ConfigEditor', () => {
  let fixture: ComponentFixture<ConfigEditor>;
  let api: Record<'getConfig' | 'updateConfig', ReturnType<typeof vi.fn>>;
  let discovery: { discoverComponents: ReturnType<typeof vi.fn> };

  const el = () => fixture.nativeElement as HTMLElement;
  const text = (selector: string) => el().querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();
  const slot = (name: string) => el().querySelector<HTMLElement>(`section.slot[data-slot="${name}"]`)!;
  const select = (name: string) => slot(name).querySelector('select')!;
  const param = (s: string, p: string) => el().querySelector<HTMLInputElement>(`#param-${s}-${p}`)!;
  const saveButton = () => el().querySelector<HTMLButtonElement>('button.save')!;

  async function render(cfg: Observable<EnvConfig>, scan: Observable<DiscoverResult> = of(result({}))) {
    api.getConfig.mockReturnValue(cfg);
    discovery.discoverComponents.mockReturnValue(scan);
    fixture = TestBed.createComponent(ConfigEditor);
    await fixture.whenStable();
  }

  async function pick(slotName: string, qualifiedName: string) {
    select(slotName).value = qualifiedName;
    select(slotName).dispatchEvent(new Event('change'));
    await fixture.whenStable();
  }

  async function type(input: HTMLInputElement, value: string) {
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function save() {
    el().querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
  }

  beforeEach(async () => {
    api = { getConfig: vi.fn(), updateConfig: vi.fn() };
    discovery = { discoverComponents: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [ConfigEditor],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: ID }) } } },
        { provide: ConfigsService, useValue: api },
        { provide: DiscoveryService, useValue: discovery },
      ],
    }).compileComponents();
  });

  it('loads the config from the route and scans the saved modules', async () => {
    await render(of(config()));
    expect(api.getConfig).toHaveBeenCalledWith({ configId: ID });
    expect(discovery.discoverComponents).toHaveBeenCalledWith({ discoverRequest: {} });
    expect(el().querySelector<HTMLInputElement>('#config-name')!.value).toBe('Kickoff');
    expect(el().querySelectorAll('section.slot')).toHaveLength(8);
  });

  it('offers the discovered components of the matching kind', async () => {
    await render(of(config()), of(result({ [Kind.RewardFunction]: [GOAL_REWARD, TOUCH_REWARD] })));
    const options = [...select('reward_fn').options].map((o) => o.textContent!.trim());
    expect(options).toEqual([
      '— Choose a component —', 'GoalReward (my_bot.rewards)', 'TouchReward (my_bot.rewards)',
    ]);
    expect(select('termination_cond').options[0].textContent).toContain('None');   // optional slot
  });

  it("shows a form for the chosen component's arguments and flags required ones left empty", async () => {
    await render(of(config()), of(result({ [Kind.RewardFunction]: [GOAL_REWARD] })));
    expect(text('.progress')).toContain('5 required parts to choose');

    await pick('reward_fn', GOAL_REWARD.qualified_name);
    expect(param('reward_fn', 'weight').placeholder).toBe('1.0');
    expect(param('reward_fn', 'team').getAttribute('aria-invalid')).toBe('true');
    expect(text('.progress')).toContain('4 required parts to choose · 1 required argument to fill in');

    await type(param('reward_fn', 'team'), ' 1 ');
    expect(param('reward_fn', 'team').getAttribute('aria-invalid')).toBe('false');
    expect(text('.progress')).not.toContain('argument');
  });

  it('saves the name, choices and non-empty arguments', async () => {
    await render(of(config()), of(result({ [Kind.RewardFunction]: [GOAL_REWARD] })));
    expect(saveButton().disabled).toBe(true);                 // nothing changed yet

    await pick('reward_fn', GOAL_REWARD.qualified_name);
    await type(param('reward_fn', 'team'), '1');
    await type(param('reward_fn', 'weight'), '');            // left empty: the default applies
    await type(el().querySelector<HTMLInputElement>('#config-name')!, ' Kickoff v2 ');
    expect(text('.save-status')).toBe('Unsaved changes');

    const saved = config({ reward_fn: { qualified_name: GOAL_REWARD.qualified_name, params: { team: '1' } } }, 'Kickoff v2');
    api.updateConfig.mockReturnValue(of(saved));
    await save();

    expect(api.updateConfig).toHaveBeenCalledWith({
      configId: ID,
      configIn: {
        name: 'Kickoff v2',
        components: { reward_fn: { qualified_name: GOAL_REWARD.qualified_name, params: { team: '1' } } },
      },
    });
    expect(text('.save-status')).toBe('Saved.');
    expect(saveButton().disabled).toBe(true);
  });

  it('drops the arguments when another component is picked, and can clear a slot', async () => {
    const saved = config({ reward_fn: { qualified_name: GOAL_REWARD.qualified_name, params: { team: '1' } } });
    await render(of(saved), of(result({ [Kind.RewardFunction]: [GOAL_REWARD, TOUCH_REWARD] })));
    expect(param('reward_fn', 'team').value).toBe('1');

    await pick('reward_fn', TOUCH_REWARD.qualified_name);
    expect(slot('reward_fn').textContent).toContain('No constructor arguments.');

    await pick('reward_fn', GOAL_REWARD.qualified_name);
    expect(param('reward_fn', 'team').value).toBe('');

    await pick('reward_fn', '');
    expect(slot('reward_fn').querySelector('.param')).toBeNull();
  });

  it('can discard unsaved changes', async () => {
    await render(of(config()), of(result({ [Kind.RewardFunction]: [GOAL_REWARD] })));
    await pick('reward_fn', GOAL_REWARD.qualified_name);
    el().querySelector<HTMLButtonElement>('button.discard')!.click();
    await fixture.whenStable();
    expect(select('reward_fn').value).toBe('');
    expect(saveButton().disabled).toBe(true);
  });

  it('keeps a saved component that the scan no longer finds', async () => {
    const saved = config({ reward_fn: { qualified_name: 'old_bot.Gone', params: { scale: '2' } } });
    await render(of(saved));
    expect(select('reward_fn').value).toBe('old_bot.Gone');
    expect(text(`section.slot[data-slot="reward_fn"] .not-found`)).toContain("wasn't found in the last scan");
    expect(param('reward_fn', 'scale').value).toBe('2');
  });

  it("shows the backend's reason when saving fails", async () => {
    await render(of(config()));
    api.updateConfig.mockReturnValue(throwError(() => new HttpErrorResponse({
      status: 409, error: { detail: "A config named 'Other' already exists" },
    })));
    await type(el().querySelector<HTMLInputElement>('#config-name')!, 'other');
    await save();
    expect(text('.save-status')).toBe("A config named 'Other' already exists");
    expect(el().querySelector<HTMLInputElement>('#config-name')!.value).toBe('other');   // kept to fix
  });

  it('still edits the config when no interpreter is selected', async () => {
    await render(of(config()), throwError(() => new HttpErrorResponse({ status: 409 })));
    expect(text('.notice')).toContain('No Python interpreter selected yet');
    expect(el().querySelectorAll('section.slot')).toHaveLength(8);
  });

  it('says when the config does not exist', async () => {
    await render(throwError(() => new HttpErrorResponse({ status: 404 })));
    expect(text('.notice')).toContain("This config doesn't exist anymore.");
    expect(el().querySelector('form')).toBeNull();
  });
});
