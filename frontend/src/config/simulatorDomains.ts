/**
 * Single source of truth for Supply chain vs Telecom simulator grouping.
 * Path segments match React routes: /simulators/:id
 */

import type { LucideIcon } from 'lucide-react';
import { Building2, ClipboardList, Database, Factory, Globe, Receipt, Server, Signal, Smartphone } from 'lucide-react';

export type SimulatorDomainId = 'supply-chain' | 'telecom';

export type SimulatorTabId =
  | 'sfdc'
  | 'oracle-erp'
  | 'sap'
  | 'external'
  | 'tpm'
  | 'sourcing'
  | 'bss'
  | 'nss'
  | 'oss';

export type SimulatorRegistryServiceKey =
  | 'sfdc'
  | 'oracle'
  | 'sap'
  | 'external'
  | 'tpm'
  | 'sourcing'
  | 'bss'
  | 'nss'
  | 'oss';

export type SimulatorEntry = {
  tabId: SimulatorTabId;
  pathSegment: string;
  label: string;
  icon: LucideIcon;
  serviceKey: SimulatorRegistryServiceKey;
};

export type SimulatorDomain = {
  id: SimulatorDomainId;
  title: string;
  description: string;
  simulators: SimulatorEntry[];
};

/** URL / legacy id aliases → canonical tab id */
export const TAB_ROUTE_ALIASES: Record<string, SimulatorTabId> = {
  sfdc: 'sfdc',
  'oracle-erp': 'oracle-erp',
  oracle: 'oracle-erp',
  sap: 'sap',
  external: 'external',
  tpm: 'tpm',
  sourcing: 'sourcing',
  bss: 'bss',
  nss: 'nss',
  oss: 'oss',
  // Legacy URLs redirect to the telecom domain default (BSS).
  'telco-sources': 'bss',
  telco_sources: 'bss',
  'telco-golden': 'bss',
  telco_golden: 'bss',
};

const SUPPLY_CHAIN_SIMULATORS: SimulatorEntry[] = [
  {
    tabId: 'sfdc',
    pathSegment: 'sfdc',
    label: 'Salesforce Simulator',
    icon: Database,
    serviceKey: 'sfdc',
  },
  {
    tabId: 'oracle-erp',
    pathSegment: 'oracle-erp',
    label: 'Oracle ERP Simulator',
    icon: Building2,
    serviceKey: 'oracle',
  },
  {
    tabId: 'sap',
    pathSegment: 'sap',
    label: 'SAP Simulator',
    icon: Factory,
    serviceKey: 'sap',
  },
  {
    tabId: 'external',
    pathSegment: 'external',
    label: 'External Sources',
    icon: Globe,
    serviceKey: 'external',
  },
  {
    tabId: 'tpm',
    pathSegment: 'tpm',
    label: 'TPM Simulator (Trade CPQ)',
    icon: Receipt,
    serviceKey: 'tpm',
  },
  {
    tabId: 'sourcing',
    pathSegment: 'sourcing',
    label: 'Sourcing Simulator (Buy CPQ)',
    icon: ClipboardList,
    serviceKey: 'sourcing',
  },
];

const TELECOM_SIMULATORS: SimulatorEntry[] = [
  {
    tabId: 'bss',
    pathSegment: 'bss',
    label: 'BSS Simulator',
    icon: Smartphone,
    serviceKey: 'bss',
  },
  {
    tabId: 'nss',
    pathSegment: 'nss',
    label: 'NSS Simulator',
    icon: Signal,
    serviceKey: 'nss',
  },
  {
    tabId: 'oss',
    pathSegment: 'oss',
    label: 'OSS Simulator',
    icon: Server,
    serviceKey: 'oss',
  },
];

export const SIMULATOR_DOMAINS: SimulatorDomain[] = [
  {
    id: 'supply-chain',
    title: 'Supply chain',
    description: 'ERP, CPQ, CRM, and external feeds for planning and fulfilment.',
    simulators: SUPPLY_CHAIN_SIMULATORS,
  },
  {
    id: 'telecom',
    title: 'Telecom',
    description: 'BSS, NSS, and OSS with Telco AI Backbone–aligned Table / File / API / Stream generation.',
    simulators: TELECOM_SIMULATORS,
  },
];

const ENTRY_BY_TAB: Map<SimulatorTabId, SimulatorEntry> = new Map();
const DOMAIN_BY_TAB: Map<SimulatorTabId, SimulatorDomainId> = new Map();

for (const domain of SIMULATOR_DOMAINS) {
  for (const sim of domain.simulators) {
    ENTRY_BY_TAB.set(sim.tabId, sim);
    DOMAIN_BY_TAB.set(sim.tabId, domain.id);
  }
}

export function getDomainForTab(tabId: SimulatorTabId): SimulatorDomainId | undefined {
  return DOMAIN_BY_TAB.get(tabId);
}

export function getSimulatorEntry(tabId: SimulatorTabId): SimulatorEntry | undefined {
  return ENTRY_BY_TAB.get(tabId);
}

/** Resolve :id from the URL (supports oracle, telco_golden, etc.) */
export function resolveTabFromRouteParam(param: string | undefined): SimulatorTabId | undefined {
  if (!param) return undefined;
  return TAB_ROUTE_ALIASES[param];
}

export function firstTabInDomain(domainId: SimulatorDomainId): SimulatorTabId {
  const d = SIMULATOR_DOMAINS.find((x) => x.id === domainId);
  return d?.simulators[0]?.tabId ?? 'sfdc';
}

/** Default landing for /simulators with no :id — first supply-chain simulator. */
export const DEFAULT_SIMULATORS_TAB: SimulatorTabId = firstTabInDomain('supply-chain');

export function pathForSimulator(tabId: SimulatorTabId): string {
  const entry = ENTRY_BY_TAB.get(tabId);
  return entry ? `/simulators/${entry.pathSegment}` : '/simulators';
}
