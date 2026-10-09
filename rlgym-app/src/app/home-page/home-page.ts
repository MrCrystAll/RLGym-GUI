import { Component, inject } from '@angular/core';
import { LINKS } from '../links';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, map, of } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { ApiConfiguration } from '../api/api-configuration';
import { getVersion } from '../api/functions';

@Component({
  selector: 'app-home-page',
  imports: [],
  templateUrl: './home-page.html',
  styleUrl: './home-page.css',
})
export class HomePage {
    protected links = LINKS;

  private http = inject(HttpClient);
  private cfg = inject(ApiConfiguration);

  protected version = toSignal(
    getVersion(this.http, this.cfg.rootUrl).pipe(
      map((r) => r.body.version as string | null),
      catchError(() => of(null)),
    ),
    { initialValue: undefined },
  );

  protected features = [
    { title: 'Configure', body: 'Pick observation builders, reward functions, and termination conditions from a list, then export the setup as a Python file or config.' },
    { title: 'Step through', body: 'Advance an episode one tick at a time and watch every reward term, observation, and done flag change.' },
    { title: 'Compare', body: 'Overlay two episodes or configs to find the exact step where they diverge.' },
  ];
}
