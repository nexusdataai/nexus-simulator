import React from 'react';
import { useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import UserMenu from './UserMenu';
import { Search, Bell, RefreshCw, Sun, Moon } from 'lucide-react';
import { useTheme } from '@/hooks/use-theme';
import { RefreshProvider } from '@/context/RefreshContext';

const TITLES: Record<string, string> = {
  '/': 'Simulator Overview',
  '/simulators': 'Simulators',
  '/scenarios': 'Solution Scenarios',
  '/tables': 'Tables',
  '/apis': 'Connector APIs',
  '/settings': 'Settings',
};

interface LayoutProps { children: React.ReactNode; }

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const loc = useLocation();
  const { theme, toggleTheme } = useTheme();

  const title = TITLES[loc.pathname] || Object.entries(TITLES).find(([k]) => k !== '/' && loc.pathname.startsWith(k))?.[1] || 'Nexus Simulator';

  return (
    <RefreshProvider>
      <div className="min-h-screen h-screen flex overflow-hidden bg-background text-foreground">
        <Sidebar />

        <div className="flex-1 flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 shrink-0 border-b border-border bg-card">
            <div className="flex items-center gap-3">
              <h1 className="text-[15px] font-semibold">{title}</h1>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={toggleTheme} title="Toggle theme"
                className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <button className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                <Search className="h-4 w-4" />
              </button>
              <button className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors relative">
                <Bell className="h-4 w-4" />
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500" />
              </button>
              <button className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                <RefreshCw className="h-4 w-4" />
              </button>
              <UserMenu />
            </div>
          </header>

          <main className="flex-1 overflow-auto relative">
            {children}
          </main>
        </div>
      </div>
    </RefreshProvider>
  );
};

export default Layout;
