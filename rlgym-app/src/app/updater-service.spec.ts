import { TestBed } from '@angular/core/testing';

import { UpdaterService } from './updater-service';
import type { UpdateState } from '../electron';

describe('UpdaterService', () => {
  let service: UpdaterService;
  let emit: (s: UpdateState) => void;

  beforeEach(() => {
    window.rlgym = {
      getBackendConfig: vi.fn(),
      openFile: vi.fn(),
      updater: {
        check: vi.fn(),
        download: vi.fn(),
        install: vi.fn(),
        onState: (cb) => {
          emit = cb;
          return () => {};
        },
      },
    };
    TestBed.configureTestingModule({});
    service = TestBed.inject(UpdaterService);
  });

  afterEach(() => {
    delete window.rlgym;
  });

  it('follows the state sent by Electron', () => {
    emit({ status: 'checking' });
    expect(service.state()).toEqual({ status: 'checking' });
  });

  it('remembers the offered release through the download', () => {
    const release = { version: '0.2.0', notes: '<p>Notes</p>', date: '2026-10-17T10:00:00Z' };

    emit({ status: 'available', ...release });
    expect(service.release()).toEqual(release);

    emit({ status: 'downloading', percent: 50 });
    expect(service.release()).toEqual(release);

    emit({ status: 'ready', ...release });
    expect(service.release()).toEqual(release);
  });

  it('forgets the release once up to date', () => {
    emit({ status: 'available', version: '0.2.0', notes: null, date: null });
    emit({ status: 'up-to-date' });
    expect(service.release()).toBeNull();
  });
});
