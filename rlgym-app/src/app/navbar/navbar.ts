import { Component } from '@angular/core';
import { LINKS } from '../links';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { UpdaterButton } from '../updater-button/updater-button';

@Component({
  selector: 'app-navbar',
  imports: [RouterLink, RouterLinkActive, UpdaterButton],
  templateUrl: './navbar.html',
  styleUrl: './navbar.css',
})
export class Navbar {
    protected links = LINKS;
  // Add an entry here whenever you add a page to app.routes.ts
    protected items = [{ label: 'Home', path: '/' }];
}
