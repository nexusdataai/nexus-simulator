/**
 * Single source of truth for navigation.
 * Used by the sidebar, mobile navigation, breadcrumbs and the command palette.
 */
import type { IconName } from '@/components/ds/Icon';
import { SIMULATORS } from '@/config/simulators';

export interface NavItem {
  id: string;
  name: string;
  path: string;
  icon: IconName;
  hint?: string;
  /** Extra path prefixes that should highlight this item. */
  match?: string[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Simulator',
    items: [
      { id: 'overview', name: 'Overview', path: '/', icon: 'home', hint: 'All simulated systems at a glance' },
      { id: 'systems', name: 'Systems', path: '/simulators', icon: 'server', hint: 'Load, seed and browse one system', match: ['/simulators/'] },
      { id: 'scenarios', name: 'Scenarios', path: '/scenarios', icon: 'route', hint: 'Overlay business situations on the data' },
    ],
  },
  {
    label: 'Data',
    items: [
      { id: 'tables', name: 'Tables', path: '/tables', icon: 'table', hint: 'Every table across all systems' },
      { id: 'apis', name: 'Vendor APIs', path: '/apis', icon: 'plug', hint: 'Salesforce, Oracle and SAP style endpoints' },
    ],
  },
];

export const SETTINGS_ITEM: NavItem = {
  id: 'settings', name: 'Settings', path: '/settings', icon: 'settings', hint: 'Service health and catalog',
};

export const ALL_NAV_ITEMS: NavItem[] = [...NAV_GROUPS.flatMap(g => g.items), SETTINGS_ITEM];

/** Destinations shown in the phone bottom bar. */
export const MOBILE_TAB_IDS = ['overview', 'systems', 'scenarios', 'tables'];

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (item.path === '/') return pathname === '/';
  if (pathname === item.path || pathname.startsWith(item.path + '/')) return true;
  return (item.match || []).some(m => pathname.startsWith(m));
}

export interface Crumb { label: string; path?: string }

export function getBreadcrumbs(pathname: string): Crumb[] {
  const root: Crumb = { label: 'Simulator', path: '/' };
  const item = ALL_NAV_ITEMS.find(i => isNavItemActive(i, pathname));
  if (!item) return [root, { label: 'Not found' }];
  const crumbs: Crumb[] = [root, { label: item.name, path: item.path }];
  const m = pathname.match(/^\/simulators\/([^/]+)/);
  if (m) {
    const sim = SIMULATORS.find(s => s.id === m[1]);
    if (sim) crumbs.push({ label: sim.name });
  }
  return crumbs;
}

export function getPageTitle(pathname: string): string {
  const crumbs = getBreadcrumbs(pathname);
  return crumbs[crumbs.length - 1].label;
}
