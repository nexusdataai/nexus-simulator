import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '@/components/Layout';
import { SFDCSimulatorPanel } from '@/components/sfdc-simulator';
import { OracleERPSimulatorPanel } from '@/components/oracle-erp-simulator';
import { SAPSimulatorPanel } from '@/components/sap-simulator';
import { ExternalSimulatorPanel } from '@/components/external-simulator';
import { CPQSimulatorPanel } from '@/components/cpq-simulator/CPQSimulatorPanel';
import { TelcoBackbonePanel } from '@/components/telco-simulator/TelcoBackbonePanel';
import {
  tpmSimulatorService,
  sourcingSimulatorService,
  bssSimulatorService,
  nssSimulatorService,
  ossSimulatorService,
} from '@/services/cpqSimulatorService';
import { cn } from '@/lib/utils';
import {
  SIMULATOR_DOMAINS,
  type SimulatorDomainId,
  type SimulatorTabId,
  DEFAULT_SIMULATORS_TAB,
  firstTabInDomain,
  getDomainForTab,
  resolveTabFromRouteParam,
  pathForSimulator,
} from '@/config/simulatorDomains';

const LAST_TAB_KEY = 'nexus-simulator:last-tab-by-domain';

function readLastTabPerDomain(): Partial<Record<SimulatorDomainId, SimulatorTabId>> {
  try {
    const raw = sessionStorage.getItem(LAST_TAB_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Partial<Record<SimulatorDomainId, SimulatorTabId>>;
  } catch {
    return {};
  }
}

function writeLastTab(domain: SimulatorDomainId, tabId: SimulatorTabId) {
  try {
    const cur = readLastTabPerDomain();
    cur[domain] = tabId;
    sessionStorage.setItem(LAST_TAB_KEY, JSON.stringify(cur));
  } catch {
    /* ignore */
  }
}

export default function SimulatorsPage() {
  const { id } = useParams();
  const nav = useNavigate();

  const resolvedFromUrl = useMemo(() => resolveTabFromRouteParam(id), [id]);

  const [activeDomain, setActiveDomain] = useState<SimulatorDomainId>(() => {
    if (resolvedFromUrl && getDomainForTab(resolvedFromUrl)) {
      return getDomainForTab(resolvedFromUrl)!;
    }
    return 'supply-chain';
  });

  const [activeTab, setActiveTab] = useState<SimulatorTabId>(() => {
    if (resolvedFromUrl) return resolvedFromUrl;
    return DEFAULT_SIMULATORS_TAB;
  });

  /** /simulators (no :id) → default supply-chain tab. */
  useEffect(() => {
    if (!id) {
      nav(pathForSimulator(DEFAULT_SIMULATORS_TAB), { replace: true });
    }
  }, [id, nav]);

  /** Sync domain + tab from URL on load or when :id changes */
  useEffect(() => {
    if (!id) return;
    const tab = resolveTabFromRouteParam(id);
    if (!tab) {
      nav(pathForSimulator(DEFAULT_SIMULATORS_TAB), { replace: true });
      return;
    }
    const dom = getDomainForTab(tab);
    if (!dom) {
      nav(pathForSimulator(DEFAULT_SIMULATORS_TAB), { replace: true });
      return;
    }
    setActiveDomain(dom);
    setActiveTab(tab);
    writeLastTab(dom, tab);
  }, [id, nav]);

  const simulatorsInDomain = useMemo(() => {
    return SIMULATOR_DOMAINS.find((d) => d.id === activeDomain)?.simulators ?? [];
  }, [activeDomain]);

  const onSelectDomain = (domainId: SimulatorDomainId) => {
    const last = readLastTabPerDomain()[domainId];
    const domainSims = SIMULATOR_DOMAINS.find((d) => d.id === domainId)?.simulators ?? [];
    const fallback = firstTabInDomain(domainId);
    const nextTab =
      last && domainSims.some((s) => s.tabId === last) ? last : fallback;
    setActiveDomain(domainId);
    setActiveTab(nextTab);
    writeLastTab(domainId, nextTab);
    nav(pathForSimulator(nextTab));
  };

  const onSelectSimulatorTab = (tabId: SimulatorTabId) => {
    setActiveTab(tabId);
    const dom = getDomainForTab(tabId);
    if (dom) {
      setActiveDomain(dom);
      writeLastTab(dom, tabId);
    }
    nav(pathForSimulator(tabId));
  };

  return (
    <Layout>
      <div className="h-full flex flex-col">
        <div className="border-b px-2 pt-2 pb-1 space-y-2 shrink-0">
          <div
            className="flex flex-wrap gap-1 px-1"
            role="tablist"
            aria-label="Simulator domain"
          >
            {SIMULATOR_DOMAINS.map((d) => {
              const selected = activeDomain === d.id;
              return (
                <button
                  key={d.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  id={`domain-tab-${d.id}`}
                  onClick={() => onSelectDomain(d.id)}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors border',
                    selected
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-transparent bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted',
                  )}
                >
                  {d.title}
                </button>
              );
            })}
          </div>
          <nav
            className="flex gap-1 overflow-x-auto pb-1"
            aria-label={`Simulators in ${activeDomain === 'supply-chain' ? 'Supply chain' : 'Telecom'}`}
            role="tablist"
          >
            {simulatorsInDomain.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.tabId;
              return (
                <button
                  key={tab.tabId}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  id={`sim-tab-${tab.tabId}`}
                  aria-controls={`sim-panel-${tab.tabId}`}
                  onClick={() => onSelectSimulatorTab(tab.tabId)}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                    active
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="flex-1 overflow-auto">
          {activeTab === 'sfdc' && (
            <div id="sim-panel-sfdc" role="tabpanel" aria-labelledby="sim-tab-sfdc">
              <SFDCSimulatorPanel />
            </div>
          )}
          {activeTab === 'oracle-erp' && (
            <div id="sim-panel-oracle-erp" role="tabpanel" aria-labelledby="sim-tab-oracle-erp">
              <OracleERPSimulatorPanel />
            </div>
          )}
          {activeTab === 'sap' && (
            <div id="sim-panel-sap" role="tabpanel" aria-labelledby="sim-tab-sap">
              <SAPSimulatorPanel />
            </div>
          )}
          {activeTab === 'external' && (
            <div id="sim-panel-external" role="tabpanel" aria-labelledby="sim-tab-external">
              <ExternalSimulatorPanel />
            </div>
          )}
          {activeTab === 'tpm' && (
            <div id="sim-panel-tpm" role="tabpanel" aria-labelledby="sim-tab-tpm">
              <CPQSimulatorPanel
                service={tpmSimulatorService}
                title="TPM Simulator"
                subtitle="Trade Promotion Management simulator — backs the sell-side Trade CPQ module (Quote_Header, Product_Offering, Price_Book, Configuration_Rule)"
              />
            </div>
          )}
          {activeTab === 'sourcing' && (
            <div id="sim-panel-sourcing" role="tabpanel" aria-labelledby="sim-tab-sourcing">
              <CPQSimulatorPanel
                service={sourcingSimulatorService}
                title="Sourcing Simulator"
                subtitle="SAP Ariba-style sourcing simulator — backs the buy-side Sourcing CPQ module (RFx_Event, Vendor_Quote, Sourcing_Scenario, Should_Cost_Model)"
              />
            </div>
          )}
          {activeTab === 'bss' && (
            <div id="sim-panel-bss" role="tabpanel" aria-labelledby="sim-tab-bss">
              <TelcoBackbonePanel
                apiBase="/api/v1/bss-simulator"
                simulatorService={bssSimulatorService}
                simulatorTitle="BSS Simulator"
                simulatorSubtitle="Business Support Systems — CRM, billing, care, campaigns, MNP"
              />
            </div>
          )}
          {activeTab === 'nss' && (
            <div id="sim-panel-nss" role="tabpanel" aria-labelledby="sim-tab-nss">
              <TelcoBackbonePanel
                apiBase="/api/v1/nss-simulator"
                simulatorService={nssSimulatorService}
                simulatorTitle="NSS Simulator"
                simulatorSubtitle="Network Switching Subsystem — usage aggregates, QoE, attach and VoLTE failures, policy throttle"
              />
            </div>
          )}
          {activeTab === 'oss' && (
            <div id="sim-panel-oss" role="tabpanel" aria-labelledby="sim-tab-oss">
              <TelcoBackbonePanel
                apiBase="/api/v1/oss-simulator"
                simulatorService={ossSimulatorService}
                simulatorTitle="OSS Simulator"
                simulatorSubtitle="Operations Support Systems — cell KPIs, alarms, maintenance, trouble tickets"
              />
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
