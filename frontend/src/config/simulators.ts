/**
 * The simulated systems this service hosts.
 * `id` is the URL segment (/simulators/:id), `service` is the key the backend
 * uses in /api/v1/simulators, `apiPath` is the system's own API root.
 */
export type DomainId = 'supply-chain' | 'telecom';

export type SimAction = 'load' | 'seed' | 'reset';

export interface SimulatorDef {
  id: string;
  service: string;
  name: string;
  /** Short name for tight places (chips, table cells). */
  short: string;
  description: string;
  apiPath: string;
  domain: DomainId;
  /** Key understood by <SystemLogo>. */
  logo: string;
  /** Data actions the system supports. Telecom systems use the backbone generator instead. */
  actions: SimAction[];
  /** Telecom layers are generated from the Telco AI Backbone atlas. */
  backbone?: boolean;
  /** Google Drive, social listening and uploads (not warehouse tables). */
  artifacts?: boolean;
}

export const DOMAINS: { id: DomainId; title: string; description: string }[] = [
  { id: 'supply-chain', title: 'Supply chain', description: 'ERP, CPQ, CRM and external feeds for planning and fulfilment.' },
  { id: 'telecom', title: 'Telecom', description: 'BSS, NSS and OSS layers generated from the Telco AI Backbone as tables, files, APIs and streams.' },
];

export const SIMULATORS: SimulatorDef[] = [
  { id: 'sfdc', service: 'sfdc', name: 'Salesforce', short: 'Salesforce', description: 'CRM objects: accounts, opportunities, campaigns and the full sObject catalog.', apiPath: '/api/v1/sfdc-simulator', domain: 'supply-chain', logo: 'salesforce', actions: ['load', 'reset'] },
  { id: 'oracle-erp', service: 'oracle', name: 'Oracle ERP', short: 'Oracle', description: 'Finance and operations: receivables, customers and purchase orders.', apiPath: '/api/v1/oracle-erp-simulator', domain: 'supply-chain', logo: 'oracle', actions: ['load', 'reset'] },
  { id: 'sap', service: 'sap', name: 'SAP S/4HANA', short: 'SAP', description: 'Supply chain operations: materials, deliveries, production and inventory.', apiPath: '/api/v1/sap-simulator', domain: 'supply-chain', logo: 'sap', actions: ['load', 'reset'] },
  { id: 'external', service: 'external', name: 'External sources', short: 'External', description: 'Google Drive documents, social listening feeds and scanned uploads — before ontology mapping.', apiPath: '/api/v1/external-simulator', domain: 'supply-chain', logo: 'external', actions: ['seed', 'reset'], artifacts: true },
  { id: 'tpm', service: 'tpm', name: 'TPM (Trade CPQ)', short: 'TPM', description: 'Trade promotion management behind sell-side CPQ: quotes, offerings, price books and rules.', apiPath: '/api/v1/tpm-simulator', domain: 'supply-chain', logo: 'tpm', actions: ['seed', 'load', 'reset'] },
  { id: 'sourcing', service: 'sourcing', name: 'Sourcing (Buy CPQ)', short: 'Sourcing', description: 'SAP Ariba style sourcing behind buy-side CPQ: RFx events, vendor quotes and should-cost models.', apiPath: '/api/v1/sourcing-simulator', domain: 'supply-chain', logo: 'sourcing', actions: ['seed', 'load', 'reset'] },
  { id: 'bss', service: 'bss', name: 'BSS', short: 'BSS', description: 'Business support systems: CRM, billing, care, campaigns and number porting.', apiPath: '/api/v1/bss-simulator', domain: 'telecom', logo: 'bss', actions: [], backbone: true },
  { id: 'nss', service: 'nss', name: 'NSS', short: 'NSS', description: 'Network switching: usage aggregates, quality of experience, attach and VoLTE failures, policy throttling.', apiPath: '/api/v1/nss-simulator', domain: 'telecom', logo: 'nss', actions: [], backbone: true },
  { id: 'oss', service: 'oss', name: 'OSS', short: 'OSS', description: 'Operations support systems: cell KPIs, alarms, maintenance and trouble tickets.', apiPath: '/api/v1/oss-simulator', domain: 'telecom', logo: 'oss', actions: [], backbone: true },
];

export const DEFAULT_SIM = SIMULATORS[0].id;

export function simById(id?: string | null): SimulatorDef | undefined {
  return SIMULATORS.find(s => s.id === id);
}

/** Find a system by the backend's service key ("oracle", "sfdc", ...). */
export function simByService(service?: string | null): SimulatorDef | undefined {
  const key = String(service || '').toLowerCase();
  return SIMULATORS.find(s => s.service === key || s.id === key);
}

export function simName(service?: string | null): string {
  return simByService(service)?.name || String(service || '');
}
