import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'home' },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home').then((m) => m.HomeComponent),
  },
  {
    path: 'board',
    loadComponent: () => import('./features/board/board').then((m) => m.BoardComponent),
  },
  {
    path: 'backlog',
    loadComponent: () => import('./features/backlog/backlog').then((m) => m.BacklogComponent),
  },
  {
    path: 'timeline',
    loadComponent: () => import('./features/timeline/timeline').then((m) => m.TimelineComponent),
  },
  {
    path: 'list',
    loadComponent: () => import('./features/list/list').then((m) => m.ListComponent),
  },
  {
    path: 'reports',
    loadComponent: () => import('./features/reports/reports').then((m) => m.ReportsComponent),
  },
  {
    path: 'inbox',
    loadComponent: () => import('./features/inbox/inbox').then((m) => m.InboxComponent),
  },
  {
    path: 'calendar',
    loadComponent: () => import('./features/calendar/calendar').then((m) => m.CalendarComponent),
  },
  {
    path: 'recaps',
    loadComponent: () => import('./features/recaps/recaps').then((m) => m.RecapsComponent),
  },
  {
    path: 'monday',
    loadComponent: () => import('./features/monday/monday').then((m) => m.MondayComponent),
  },
  {
    path: 'issues/:key',
    loadComponent: () =>
      import('./features/issue-detail/issue-detail').then((m) => m.IssueDetailComponent),
  },
  {
    path: 'category/:field/:value',
    loadComponent: () => import('./features/category/category').then((m) => m.CategoryComponent),
  },
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings').then((m) => m.SettingsComponent),
  },
  { path: '**', redirectTo: 'home' },
];
