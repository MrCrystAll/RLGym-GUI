import { Component, inject } from '@angular/core';
import { UpdateState } from '../../electron';
import { UpdaterService } from '../updater-service';

@Component({
  selector: 'app-home-page',
  imports: [],
  templateUrl: './home-page.html',
  styleUrl: './home-page.css',
})
export class HomePage {
  readonly updaterService: UpdaterService = inject(UpdaterService)
}
