import { Component } from '@angular/core';
import { HomeComponent } from './home/home.component';

// Shell minimo: a aplicacao e uma pagina unica (HomeComponent).
@Component({
  selector: 'app-root',
  imports: [HomeComponent],
  template: `<app-home />`,
})
export class AppComponent {}
