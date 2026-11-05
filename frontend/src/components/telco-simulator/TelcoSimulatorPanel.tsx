import { CPQSimulatorPanel } from '../cpq-simulator/CPQSimulatorPanel';
import type { CPQSimulatorService } from '../../services/cpqSimulatorService';

interface Props {
  service: CPQSimulatorService;
  title: string;
  subtitle: string;
}

/** Thin wrapper so telco tabs share the CPQ/SAP admin panel chrome. */
export function TelcoSimulatorPanel({ service, title, subtitle }: Props) {
  return <CPQSimulatorPanel service={service} title={title} subtitle={subtitle} />;
}
