import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';
import { ThemeProvider, useTheme } from '@/hooks/use-theme';
import { TooltipProvider } from '@/components/ui/tooltip';
import { ConfirmHost } from '@/components/ds/confirm';
import Layout from '@/components/Layout';
import OverviewPage from '@/pages/OverviewPage';
import SystemsPage from '@/pages/SystemsPage';
import ScenariosPage from '@/pages/ScenariosPage';
import TablesPage from '@/pages/TablesPage';
import ApisPage from '@/pages/ApisPage';
import SettingsPage from '@/pages/SettingsPage';
import NotFoundPage from '@/pages/NotFoundPage';

function Toasts() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="bottom-right" closeButton toastOptions={{ className: 'font-sans' }} />;
}

/** Same routes as the previous front end, so existing links keep working. */
export default function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={200}>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/simulators" element={<SystemsPage />} />
              <Route path="/simulators/:id" element={<SystemsPage />} />
              <Route path="/operations/simulators" element={<Navigate to="/simulators" replace />} />
              <Route path="/scenarios" element={<ScenariosPage />} />
              <Route path="/tables" element={<TablesPage />} />
              <Route path="/apis" element={<ApisPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Layout>
          <ConfirmHost />
          <Toasts />
        </BrowserRouter>
      </TooltipProvider>
    </ThemeProvider>
  );
}
