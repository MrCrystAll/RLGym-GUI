import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';

import { ConfigExportDialog } from './config-export';
import { ConfigExport, ConfigExportMissingSlotsEnum as Slot, ConfigsService, ExportFormat } from '../api';

const ID = 'a'.repeat(32);

function exported(format: ExportFormat, missing: Slot[] = []): ConfigExport {
  const files = { snippet: 'kickoff.py', script: 'run_kickoff.py', json: 'kickoff.json' };
  return { format, filename: files[format], content: `content as ${format}`, missing_slots: missing };
}

describe('ConfigExportDialog', () => {
  let fixture: ComponentFixture<ConfigExportDialog>;
  let api: { exportConfig: ReturnType<typeof vi.fn> };
  let closed: number;

  const el = () => fixture.nativeElement as HTMLElement;
  const text = (selector: string) => el().querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim();
  const radio = (format: ExportFormat) => el().querySelector<HTMLInputElement>(`input[value="${format}"]`)!;

  async function render() {
    fixture = TestBed.createComponent(ConfigExportDialog);
    fixture.componentRef.setInput('configId', ID);
    closed = 0;
    fixture.componentInstance.closed.subscribe(() => closed++);
    await fixture.whenStable();
  }

  async function pick(format: ExportFormat) {
    radio(format).click();
    await fixture.whenStable();
  }

  beforeEach(async () => {
    api = { exportConfig: vi.fn(({ format }) => of(exported(format))) };
    await TestBed.configureTestingModule({
      imports: [ConfigExportDialog],
      providers: [{ provide: ConfigsService, useValue: api }],
    }).compileComponents();
  });

  afterEach(() => {
    delete window.rlgym;
  });

  it('previews the Python snippet first', async () => {
    await render();
    expect(api.exportConfig).toHaveBeenCalledWith({ configId: ID, format: ExportFormat.Snippet });
    expect(radio(ExportFormat.Snippet).checked).toBe(true);
    expect(text('.preview')).toBe('content as snippet');
    expect(el().textContent).toContain('kickoff.py');
  });

  it('switches format', async () => {
    await render();
    await pick(ExportFormat.Script);
    expect(api.exportConfig).toHaveBeenLastCalledWith({ configId: ID, format: ExportFormat.Script });
    expect(text('.preview')).toBe('content as script');
    await pick(ExportFormat.Json);
    expect(text('.preview')).toBe('content as json');
    expect(el().textContent).toContain('kickoff.json');
  });

  it('warns about missing parts in the Python formats only', async () => {
    api.exportConfig.mockImplementation(({ format }) => of(exported(format, [Slot.TransitionEngine])));
    await render();
    expect(text('.missing')).toContain('Not chosen yet: transition_engine');
    await pick(ExportFormat.Json);
    expect(el().querySelector('.missing')).toBeNull();
  });

  it('saves through the native dialog and says where', async () => {
    const saveFile = vi.fn().mockResolvedValue('C:\\bots\\kickoff.py');
    window.rlgym = { saveFile } as unknown as typeof window.rlgym;
    await render();
    el().querySelector<HTMLButtonElement>('button.save-file')!.click();
    await fixture.whenStable();
    expect(saveFile).toHaveBeenCalledWith({
      title: 'Export config',
      defaultName: 'kickoff.py',
      filters: [{ name: 'Python', extensions: ['py'] }],
      content: 'content as snippet',
    });
    expect(text('.export-status')).toBe('Saved to C:\\bots\\kickoff.py');
  });

  it('says nothing when the save dialog is cancelled', async () => {
    window.rlgym = { saveFile: vi.fn().mockResolvedValue(null) } as unknown as typeof window.rlgym;
    await render();
    el().querySelector<HTMLButtonElement>('button.save-file')!.click();
    await fixture.whenStable();
    expect(text('.export-status')).toBe('');
  });

  it('copies the content', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    await render();
    el().querySelector<HTMLButtonElement>('button.copy')!.click();
    await fixture.whenStable();
    expect(writeText).toHaveBeenCalledWith('content as snippet');
    expect(text('.export-status')).toBe('Copied to the clipboard.');
    vi.unstubAllGlobals();
  });

  it("shows the backend's reason when the export fails", async () => {
    api.exportConfig.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 404, error: { detail: 'No such config' } })));
    await render();
    expect(text('[role="alert"]')).toBe('No such config');
  });

  it('closes on the close button and on Escape', async () => {
    await render();
    el().querySelector<HTMLButtonElement>('button.close')!.click();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(closed).toBe(2);
  });
});
