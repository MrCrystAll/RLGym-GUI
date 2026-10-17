import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';

import { UpdaterButton } from './updater-button';
import { UpdaterService } from '../updater-service';
import type { ReleaseInfo, UpdateState } from '../../electron';

describe('UpdaterButton', () => {
  let fixture: ComponentFixture<UpdaterButton>;
  let updates: {
    state: ReturnType<typeof signal<UpdateState>>;
    release: ReturnType<typeof signal<ReleaseInfo | null>>;
    check: ReturnType<typeof vi.fn>;
    download: ReturnType<typeof vi.fn>;
    install: ReturnType<typeof vi.fn>;
  };

  const el = () => fixture.nativeElement as HTMLElement;
  const whatsNew = () => el().querySelector<HTMLButtonElement>('button.whats-new');

  async function show(state: UpdateState, release: ReleaseInfo | null = null) {
    updates.state.set(state);
    updates.release.set(release);
    await fixture.whenStable();
  }

  beforeEach(async () => {
    updates = {
      state: signal<UpdateState>({ status: 'idle' }),
      release: signal<ReleaseInfo | null>(null),
      check: vi.fn(),
      download: vi.fn(),
      install: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [UpdaterButton],
      providers: [{ provide: UpdaterService, useValue: updates }],
    }).compileComponents();

    fixture = TestBed.createComponent(UpdaterButton);
    await fixture.whenStable();
  });

  it('renders nothing when updates are disabled', async () => {
    await show({ status: 'disabled' });
    expect(el().querySelector('button')).toBeNull();
  });

  it('has no "What\'s new" button without release notes', async () => {
    const release = { version: '0.2.0', notes: null, date: null };
    await show({ status: 'available', ...release }, release);
    expect(whatsNew()).toBeNull();
  });

  it('shows the release notes of an available update', async () => {
    const release = {
      version: '0.2.0',
      notes: '<h3>Added</h3><ul><li>Release notes in the app</li></ul>',
      date: '2026-10-17T10:00:00Z',
    };
    await show({ status: 'available', ...release }, release);

    expect(whatsNew()?.getAttribute('popovertarget')).toBe('release-notes');
    const popover = el().querySelector('#release-notes')!;
    expect(popover.textContent).toContain("What's new in v0.2.0");
    expect(popover.textContent).toContain('October 17, 2026');
    expect(popover.querySelector('li')?.textContent).toBe('Release notes in the app');
  });

  it('keeps the notes while the update downloads', async () => {
    const release = { version: '0.2.0', notes: '<p>Notes</p>', date: null };
    await show({ status: 'downloading', percent: 40 }, release);
    expect(whatsNew()).not.toBeNull();
  });

  it('sanitizes the notes', async () => {
    const release = {
      version: '0.2.0',
      notes: '<p>Fine</p><script>alert(1)</script><img src="x" onerror="alert(1)">',
      date: null,
    };
    await show({ status: 'available', ...release }, release);

    const notes = el().querySelector('#release-notes .notes')!;
    expect(notes.querySelector('script')).toBeNull();
    expect(notes.querySelector('img')?.hasAttribute('onerror')).toBe(false);
    expect(notes.textContent).toContain('Fine');
  });

  it('downloads an available update on click', async () => {
    const release = { version: '0.2.0', notes: null, date: null };
    await show({ status: 'available', ...release }, release);
    el().querySelector('button')!.click();
    expect(updates.download).toHaveBeenCalled();
  });
});
