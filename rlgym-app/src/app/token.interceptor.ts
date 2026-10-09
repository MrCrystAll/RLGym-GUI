// src/app/token.interceptor.ts
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { BackendConnection } from './backend-connection';

export const tokenInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(BackendConnection).token;
  return next(req.clone({ setHeaders: { 'X-Api-Token': token } }));
};