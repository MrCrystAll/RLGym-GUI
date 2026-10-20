import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';

import { ConfigsPage } from './configs-page';
import { ConfigSummary, ConfigSummarySlotsEnum as Slot, ConfigsService } from '../api';

const ID_A = 'a'.repeat(32);
const ID_B = 'b'.repeat(32);

function summary(id: string, name: string, slots: Slot[] = [], complete = false): ConfigSummary {
  return { id, name, slots, complete, updated_at: '2026-10-20T10:00:00Z' };
}

describe('ConfigsPage', () => {
  let fixture: ComponentFixture<ConfigsPage>;
  let api: Record<'listConfigs' | 'createConfig' | 'deleteConfig', ReturnType<typeof vi.fn>>;

  const el = () => fixture.nativeElement as HTMLElement;
  const names = () => [...el().querySelectorAll('li.config .name')].map((n) => n.textContent!.trim());
  const rowText = (i: number) => el().querySelectorAll('li.config')[i].textContent!.replace(/\s+/g, ' ');

  async function render(list: ConfigSummary[]) {
    api.listConfigs.mockReturnValue(of(list));
    fixture = TestBed.createComponent(ConfigsPage);
    await fixture.whenStable();
  }

  async function typeName(value: string) {
    const input = el().querySelector<HTMLInputElement>('#new-name')!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    await fixture.whenStable();
  }

  async function submit() {
    el().querySelector('form')!.dispatchEvent(new Event('submit'));
    await fixture.whenStable();
  }

  beforeEach(async () => {
    api = { listConfigs: vi.fn(), createConfig: vi.fn(), deleteConfig: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [ConfigsPage],
      providers: [{ provide: ConfigsService, useValue: api }],
    }).compileComponents();
  });

  it('says when there are no configs', async () => {
    await render([]);
    expect(el().querySelector('.empty')!.textContent).toContain('No configs yet');
  });

  it('lists configs with how far along they are', async () => {
    await render([
      summary(ID_A, 'Kickoff', [Slot.RewardFn, Slot.ObsBuilder]),
      summary(ID_B, 'Full', [], true),
      summary('c'.repeat(32), 'Blank'),
    ]);
    expect(names()).toEqual(['Kickoff', 'Full', 'Blank']);
    expect(rowText(0)).toContain('2 of 8 parts chosen');
    expect(rowText(1)).toContain('Complete');
    expect(rowText(2)).toContain('Empty');
    expect(rowText(0)).toContain('updated Oct 20, 2026');
  });

  it('creates a config and refreshes the list', async () => {
    await render([]);
    api.createConfig.mockReturnValue(of({}));
    api.listConfigs.mockReturnValue(of([summary(ID_A, 'Kickoff')]));

    const create = el().querySelector<HTMLButtonElement>('button.create')!;
    expect(create.disabled).toBe(true);                  // nothing typed yet
    await typeName('  Kickoff ');
    expect(create.disabled).toBe(false);
    await submit();

    expect(api.createConfig).toHaveBeenCalledWith({ configIn: { name: 'Kickoff' } });
    expect(names()).toEqual(['Kickoff']);
    expect(el().querySelector<HTMLInputElement>('#new-name')!.value).toBe('');
  });

  it("shows the backend's reason when a name is taken", async () => {
    await render([summary(ID_A, 'Kickoff')]);
    api.createConfig.mockReturnValue(throwError(() => new HttpErrorResponse({
      status: 409, error: { detail: "A config named 'kickoff' already exists" },
    })));

    await typeName('kickoff');
    await submit();

    expect(el().querySelector('#create-error')!.textContent).toContain("A config named 'kickoff' already exists");
    expect(el().querySelector<HTMLInputElement>('#new-name')!.value).toBe('kickoff');   // kept to fix
  });

  it('asks before deleting, then deletes', async () => {
    await render([summary(ID_A, 'Kickoff'), summary(ID_B, 'Other')]);
    api.deleteConfig.mockReturnValue(of(undefined));

    el().querySelector<HTMLButtonElement>('button.delete')!.click();
    await fixture.whenStable();
    expect(api.deleteConfig).not.toHaveBeenCalled();
    expect(rowText(0)).toContain('Delete?');

    api.listConfigs.mockReturnValue(of([summary(ID_B, 'Other')]));
    el().querySelector<HTMLButtonElement>('button.confirm-delete')!.click();
    await fixture.whenStable();

    expect(api.deleteConfig).toHaveBeenCalledWith({ configId: ID_A });
    expect(names()).toEqual(['Other']);
  });

  it('can cancel a delete', async () => {
    await render([summary(ID_A, 'Kickoff')]);
    el().querySelector<HTMLButtonElement>('button.delete')!.click();
    await fixture.whenStable();
    [...el().querySelectorAll('button')].find((b) => b.textContent!.trim() === 'Cancel')!.click();
    await fixture.whenStable();
    expect(el().querySelector('button.confirm-delete')).toBeNull();
    expect(api.deleteConfig).not.toHaveBeenCalled();
  });

  it('reports a backend that is unreachable', async () => {
    api.listConfigs.mockReturnValue(throwError(() => new Error('down')));
    fixture = TestBed.createComponent(ConfigsPage);
    await fixture.whenStable();
    expect(el().querySelector('[role="alert"]')!.textContent).toContain('Could not reach the backend.');
  });
});
