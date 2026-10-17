import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { Observable, of, throwError } from 'rxjs';

import { ComponentsPage } from './components-page';
import { DiscoverResult, DiscoveredComponentKindEnum as Kind, DiscoveryService } from '../api';

function result(partial: Partial<DiscoverResult['components']>, errors: DiscoverResult['errors'] = []): DiscoverResult {
  const components: DiscoverResult['components'] = {};
  for (const kind of Object.values(Kind)) components[kind] = partial[kind] ?? [];
  return { components, errors };
}

const GOAL_REWARD = {
  kind: Kind.RewardFunction,
  name: 'GoalReward',
  module: 'my_bot.rewards',
  qualified_name: 'my_bot.rewards.GoalReward',
  doc: '+weight when the given team scores.',
  params: [
    { name: 'weight', type: 'float', default: '1.0', required: false },
    { name: 'team', type: 'int', default: '0', required: false },
  ],
};
const TICK_LIMIT = {
  kind: Kind.DoneCondition,
  name: 'TickLimit',
  module: 'my_bot.done',
  qualified_name: 'my_bot.done.TickLimit',
  doc: null,
  params: [{ name: 'ticks', type: 'int', default: null, required: true }],
};

describe('ComponentsPage', () => {
  let fixture: ComponentFixture<ComponentsPage>;
  let discovery: { discoverComponents: ReturnType<typeof vi.fn> };

  const el = () => fixture.nativeElement as HTMLElement;
  const text = (selector: string) => el().querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();

  async function render(response: Observable<DiscoverResult>) {
    discovery.discoverComponents.mockReturnValue(response);
    fixture = TestBed.createComponent(ComponentsPage);
    await fixture.whenStable();
  }

  beforeEach(async () => {
    discovery = { discoverComponents: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [ComponentsPage],
      providers: [provideRouter([]), { provide: DiscoveryService, useValue: discovery }],
    }).compileComponents();
  });

  it('scans the saved modules', async () => {
    await render(of(result({})));
    expect(discovery.discoverComponents).toHaveBeenCalledWith({ discoverRequest: {} });
  });

  it('lists components under their kind, in build order', async () => {
    await render(of(result({ [Kind.RewardFunction]: [GOAL_REWARD], [Kind.DoneCondition]: [TICK_LIMIT] })));

    const headings = [...el().querySelectorAll('section.kind h2')].map((h) => h.textContent!.replace(/\s+/g, ' ').trim());
    expect(headings).toEqual([
      'Transition engines 0', 'State mutators 0', 'Observation builders 0', 'Action parsers 0',
      'Reward functions 1', 'Done conditions 1', 'Shared info providers 0',
    ]);

    const cards = el().querySelectorAll('li.component');
    expect(cards[0].querySelector('h3')!.textContent).toBe('GoalReward(weight=1.0, team=0)');
    expect(cards[0].textContent).toContain('my_bot.rewards');
    expect(cards[0].textContent).toContain('+weight when the given team scores.');
    expect(cards[1].querySelector('h3')!.textContent).toBe('TickLimit(ticks)');
    expect(cards[1].querySelector('tbody')!.textContent).toContain('required');
  });

  it('shows module import errors', async () => {
    await render(of(result(
      { [Kind.RewardFunction]: [GOAL_REWARD] },
      [{ module: 'my_bot.broken', message: 'RuntimeError: boom' }],
    )));
    expect(text('.module-errors')).toContain('1 module could not be imported');
    expect(text('.module-errors')).toContain('my_bot.broken: RuntimeError: boom');
    expect(el().querySelectorAll('li.component').length).toBe(1);
  });

  it('points to Settings when nothing was found', async () => {
    await render(of(result({})));
    expect(text('.notice')).toBe('No components found. Add the modules to scan in Settings.');
    expect(el().querySelector('section.kind')).toBeNull();
  });

  it('points to Settings when no interpreter is selected', async () => {
    await render(throwError(() => new HttpErrorResponse({ status: 409, error: { detail: 'No Python interpreter selected' } })));
    expect(text('.notice')).toBe('No Python interpreter selected yet. Choose one in Settings.');
  });

  it("shows the worker's error when the scan fails", async () => {
    await render(throwError(() => new HttpErrorResponse({
      status: 502, error: { detail: "The worker didn't answer 'discover' within 60s and was stopped (see worker.log)" },
    })));
    expect(text('[role="alert"] p:first-child')).toBe('The scan failed.');
    expect(text('[role="alert"] p.mono')).toContain("The worker didn't answer 'discover' within 60s");
  });

  it('rescans on demand', async () => {
    await render(of(result({})));
    discovery.discoverComponents.mockReturnValue(of(result({ [Kind.RewardFunction]: [GOAL_REWARD] })));

    el().querySelector<HTMLButtonElement>('button.rescan')!.click();
    await fixture.whenStable();

    expect(discovery.discoverComponents).toHaveBeenCalledTimes(2);
    expect(el().querySelectorAll('li.component').length).toBe(1);
  });
});
