import { Routes } from '@angular/router';
import { HomePage } from './home-page/home-page';
import { SettingsPage } from './settings-page/settings-page';
import { ComponentsPage } from './components-page/components-page';

export const routes: Routes = [
  { path: '', component: HomePage, title: 'RLGym GUI' },
  { path: 'components', component: ComponentsPage, title: 'Components · RLGym GUI' },
  { path: 'settings', component: SettingsPage, title: 'Settings · RLGym GUI' },
  { path: '**', redirectTo: '' },
];
