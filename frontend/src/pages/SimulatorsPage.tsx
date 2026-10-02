import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '@/components/Layout';
import { SFDCSimulatorPanel } from '@/components/sfdc-simulator';
import { OracleERPSimulatorPanel } from '@/components/oracle-erp-simulator';
import { SAPSimulatorPanel } from '@/components/sap-simulator';
import { ExternalSimulatorPanel } from '@/components/external-simulator';
import { CPQSimulatorPanel } from '@/components/cpq-simulator/CPQSimulatorPanel';
import { tpmSimulatorService, sourcingSimulatorService } from '@/services/cpqSimulatorService';
import { cn } from '@/lib/utils';
import { Database, Building2, Factory, Globe, Receipt, ClipboardList } from 'lucide-react';

type Tab = 'sfdc' | 'oracle-erp' | 'sap' | 'external' | 'tpm' | 'sourcing';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'sfdc', label: 'Salesforce Simulator', icon: Database },
  { id: 'oracle-erp', label: 'Oracle ERP Simulator', icon: Building2 },
  { id: 'sap', label: 'SAP Simulator', icon: Factory },
  { id: 'external', label: 'External Sources', icon: Globe },
  { id: 'tpm', label: 'TPM Simulator (Trade CPQ)', icon: Receipt },
  { id: 'sourcing', label: 'Sourcing Simulator (Buy CPQ)', icon: ClipboardList },
];

const TAB_BY_ID: Record<string, Tab> = {
  sfdc: 'sfdc',
  'oracle-erp': 'oracle-erp',
  oracle: 'oracle-erp',
  sap: 'sap',
  external: 'external',
  tpm: 'tpm',
  sourcing: 'sourcing',
};

export default function SimulatorsPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>(TAB_BY_ID[id || ''] || 'sfdc');

  useEffect(() => {
    if (id && TAB_BY_ID[id] && TAB_BY_ID[id] !== activeTab) {
      setActiveTab(TAB_BY_ID[id]);
    }
  }, [id, activeTab]);

  return (
    <Layout>
      <div className="h-full flex flex-col">
        {/* Tab bar */}
        <div className="border-b px-1">
          <nav className="flex gap-1 overflow-x-auto" aria-label="Simulator tabs">
            {TABS.map(tab => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    nav(`/simulators/${tab.id}`);
                  }}
                  className={cn(
                    'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                    active
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-auto">
          {activeTab === 'sfdc' && <SFDCSimulatorPanel />}
          {activeTab === 'oracle-erp' && <OracleERPSimulatorPanel />}
          {activeTab === 'sap' && <SAPSimulatorPanel />}
          {activeTab === 'external' && <ExternalSimulatorPanel />}
          {activeTab === 'tpm' && (
            <CPQSimulatorPanel
              service={tpmSimulatorService}
              title="TPM Simulator"
              subtitle="Trade Promotion Management simulator — backs the sell-side Trade CPQ module (Quote_Header, Product_Offering, Price_Book, Configuration_Rule)"
            />
          )}
          {activeTab === 'sourcing' && (
            <CPQSimulatorPanel
              service={sourcingSimulatorService}
              title="Sourcing Simulator"
              subtitle="SAP Ariba-style sourcing simulator — backs the buy-side Sourcing CPQ module (RFx_Event, Vendor_Quote, Sourcing_Scenario, Should_Cost_Model)"
            />
          )}
        </div>
      </div>
    </Layout>
  );
}
