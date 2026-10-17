import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { SettingsPage } from './settings-page';
import { DiscoveryService, PythonInfo, Settings, SettingsService } from '../api';

const OK_INFO: PythonInfo = { python: '3.12.2', executable: 'C:/py.exe', rlgym_api: '2.0.0', error: null };

describe('SettingsPage', () => {
  let fixture: ComponentFixture<SettingsPage>;
  let settingsApi: { getSettings: ReturnType<typeof vi.fn>; updateSettings: ReturnType<typeof vi.fn> };
  let discovery: { getPythonInfo: ReturnType<typeof vi.fn> };

  const el = () => fixture.nativeElement as HTMLElement;
  const status = () => el().querySelector('#python-status')!.textContent!.replace(/\s+/g, ' ').trim();
  const saveButton = () => el().querySelector<HTMLButtonElement>('button.save')!;
  const browseButton = () =>
    [...el().querySelectorAll('button')].find((b) => b.textContent!.includes('Browse'));

  function type(selector: string, value: string, change = false) {
    const input = el().querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    if (change) input.dispatchEvent(new Event('change'));
  }

  async function render(saved: Settings, info: PythonInfo = OK_INFO) {
    settingsApi.getSettings.mockReturnValue(of(saved));
    discovery.getPythonInfo.mockReturnValue(of(info));
    fixture = TestBed.createComponent(SettingsPage);
    await fixture.whenStable();
  }

  beforeEach(async () => {
    settingsApi = { getSettings: vi.fn(), updateSettings: vi.fn() };
    discovery = { getPythonInfo: vi.fn() };
    await TestBed.configureTestingModule({
      imports: [SettingsPage],
      providers: [
        { provide: SettingsService, useValue: settingsApi },
        { provide: DiscoveryService, useValue: discovery },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    delete window.rlgym;
  });

  it('shows the saved settings and checks the interpreter', async () => {
    await render({ python: 'C:/py.exe', modules: ['a.b', 'c'] });

    expect(el().querySelector<HTMLInputElement>('#python')!.value).toBe('C:/py.exe');
    expect(el().querySelector<HTMLTextAreaElement>('#modules')!.value).toBe('a.b\nc');
    expect(discovery.getPythonInfo).toHaveBeenCalledWith({ python: 'C:/py.exe' });
    expect(status()).toBe('Python 3.12.2 · rlgym-api 2.0.0');
    expect(saveButton().disabled).toBe(true);           // nothing changed yet
  });

  it('shows why an interpreter cannot be used', async () => {
    await render(
      { python: 'C:/py.exe', modules: [] },
      { python: '3.12.2', executable: 'C:/py.exe', rlgym_api: null, error: "ModuleNotFoundError: No module named 'rlgym'" },
    );
    expect(status()).toBe("Python 3.12.2 · ModuleNotFoundError: No module named 'rlgym'");
  });

  it('says when no interpreter is selected, without asking the backend', async () => {
    await render({ python: null, modules: [] });
    expect(status()).toBe('No interpreter selected.');
    expect(discovery.getPythonInfo).not.toHaveBeenCalled();
  });

  it('rechecks a path typed by hand', async () => {
    await render({ python: null, modules: [] });
    type('#python', ' D:/other.exe ', true);
    await fixture.whenStable();
    expect(discovery.getPythonInfo).toHaveBeenCalledWith({ python: 'D:/other.exe' });
    expect(status()).toContain('Python 3.12.2');
  });

  it('saves the cleaned-up values', async () => {
    await render({ python: 'C:/py.exe', modules: [] });
    settingsApi.updateSettings.mockReturnValue(of({ python: 'C:/py.exe', modules: ['a', 'b'] }));

    type('#modules', 'a\n\n  b  \n');
    await fixture.whenStable();
    expect(el().textContent).toContain('Unsaved changes');
    expect(saveButton().disabled).toBe(false);

    saveButton().click();
    await fixture.whenStable();

    expect(settingsApi.updateSettings).toHaveBeenCalledWith({
      settings: { python: 'C:/py.exe', modules: ['a', 'b'] },
    });
    expect(el().textContent).toContain('Saved.');
    expect(el().querySelector<HTMLTextAreaElement>('#modules')!.value).toBe('a\nb');
    expect(saveButton().disabled).toBe(true);
  });

  it('reports a backend that is unreachable', async () => {
    settingsApi.getSettings.mockReturnValue(throwError(() => new Error('down')));
    fixture = TestBed.createComponent(SettingsPage);
    await fixture.whenStable();
    expect(el().querySelector('[role="alert"]')!.textContent).toContain('Could not reach the backend.');
  });

  it('hides Browse outside Electron', async () => {
    await render({ python: null, modules: [] });
    expect(browseButton()).toBeUndefined();
  });

  it('fills in and checks the interpreter picked with Browse', async () => {
    const openFile = vi.fn().mockResolvedValue('C:/picked/python.exe');
    window.rlgym = { openFile } as unknown as NonNullable<typeof window.rlgym>;
    await render({ python: null, modules: [] });

    browseButton()!.click();
    await fixture.whenStable();

    expect(openFile).toHaveBeenCalled();
    expect(el().querySelector<HTMLInputElement>('#python')!.value).toBe('C:/picked/python.exe');
    expect(discovery.getPythonInfo).toHaveBeenCalledWith({ python: 'C:/picked/python.exe' });
    expect(el().textContent).toContain('Unsaved changes');
  });
});
