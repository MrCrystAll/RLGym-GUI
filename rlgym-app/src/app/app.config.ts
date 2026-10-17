import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withHashLocation } from '@angular/router';

import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { tokenInterceptor } from './token.interceptor';
import { BackendConnection } from './backend-connection';
import { Configuration, provideApi } from './api';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withHashLocation()),
    provideHttpClient(withInterceptors([tokenInterceptor])),
    // basePath is filled in below once Electron has told us the backend's port.
    provideApi({}),
    provideAppInitializer(async () => {
      const api = inject(Configuration);
      const conn = inject(BackendConnection);
      const cfg = (await window.rlgym?.getBackendConfig())
        ?? { baseUrl: 'http://127.0.0.1:8000', token: 'dev-token' };
      api.basePath = cfg.baseUrl;
      conn.token = cfg.token;
    }),
  ]
};
