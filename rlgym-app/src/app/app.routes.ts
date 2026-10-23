import { Routes } from '@angular/router';
import { HomePage } from './home-page/home-page';
import { SettingsPage } from './settings-page/settings-page';
import { ComponentsPage } from './components-page/components-page';
import { ConfigsPage } from './configs-page/configs-page';
import { ConfigEditor } from './config-editor/config-editor';

export const routes: Routes = [
  { path: '', component: HomePage, title: 'RLGym GUI' },
  { path: 'components', component: ComponentsPage, title: 'Components · RLGym GUI' },
  { path: 'configs', component: ConfigsPage, title: 'Configs · RLGym GUI' },
  { path: 'configs/:id', component: ConfigEditor, title: 'Edit config · RLGym GUI' },
  { path: 'settings', component: SettingsPage, title: 'Settings · RLGym GUI' },
  { path: '**', redirectTo: '' },
];
