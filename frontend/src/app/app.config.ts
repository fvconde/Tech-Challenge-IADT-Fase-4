import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    // habilita o HttpClient para o ApiService (chamadas a API FastAPI)
    provideHttpClient(),
  ],
};
