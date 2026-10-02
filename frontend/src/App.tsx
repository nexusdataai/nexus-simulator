import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { ThemeProvider } from "./hooks/use-theme";
import { EnterpriseAuthProvider, useEnterpriseAuth } from "./context/EnterpriseAuthContext";

import Login from "./pages/Login";
import Signup from "./pages/Signup";
import AuthCallback from "./pages/AuthCallback";
import NotFound from "./pages/NotFound";
import SimulatorsPage from "./pages/SimulatorsPage";
import SimulatorOverviewPage from "./pages/SimulatorOverviewPage";
import SimulatorTablesPage from "./pages/SimulatorTablesPage";
import SimulatorApisPage from "./pages/SimulatorApisPage";
import SimulatorScenariosPage from "./pages/SimulatorScenariosPage";
import SimulatorSettingsPage from "./pages/SimulatorSettingsPage";

const queryClient = new QueryClient();

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useEnterpriseAuth();
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const P = ({ children }: { children: React.ReactNode }) => (
  <ProtectedRoute>{children}</ProtectedRoute>
);

const AuthRoutes = () => {
  const { user, loading } = useEnterpriseAuth();

  if (user && !loading && (window.location.pathname === "/login" || window.location.pathname === "/signup")) {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      <Route path="/" element={<P><SimulatorOverviewPage /></P>} />
      <Route path="/simulators" element={<P><SimulatorsPage /></P>} />
      <Route path="/simulators/:id" element={<P><SimulatorsPage /></P>} />
      <Route path="/operations/simulators" element={<Navigate to="/simulators" replace />} />
      <Route path="/scenarios" element={<P><SimulatorScenariosPage /></P>} />
      <Route path="/tables" element={<P><SimulatorTablesPage /></P>} />
      <Route path="/apis" element={<P><SimulatorApisPage /></P>} />
      <Route path="/settings" element={<P><SimulatorSettingsPage /></P>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => {
  useEffect(() => {
    const old = localStorage.getItem("theme");
    if (old) {
      localStorage.setItem("app-theme", old);
      localStorage.removeItem("theme");
    }
  }, []);

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <EnterpriseAuthProvider>
              <AuthRoutes />
            </EnterpriseAuthProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
};

export default App;
