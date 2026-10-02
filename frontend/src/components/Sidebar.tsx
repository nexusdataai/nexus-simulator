import { useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronLeft, Database, GitBranch, Layers, Settings, Table2, Plug } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";

const MENU = [
  {
    label: "SIMULATORS",
    items: [
      { id: "home", name: "Overview", icon: Layers, path: "/" },
      { id: "systems", name: "Systems", icon: Database, path: "/simulators" },
      { id: "scenarios", name: "Scenarios", icon: GitBranch, path: "/scenarios" },
      { id: "tables", name: "Tables", icon: Table2, path: "/tables" },
      { id: "apis", name: "APIs", icon: Plug, path: "/apis" },
    ],
  },
];

const Sidebar = () => {
  const nav = useNavigate();
  const loc = useLocation();
  const [mini, setMini] = useState(false);
  const active = (p: string) => {
    if (p === "/") return loc.pathname === "/";
    return loc.pathname === p || loc.pathname.startsWith(p + "/");
  };

  return (
    <aside
      className={cn(
        "h-full flex flex-col shrink-0 transition-all duration-200 border-r relative",
        "bg-slate-100 dark:bg-[#141b2d] border-slate-200 dark:border-[#1e2740]",
        mini ? "w-14" : "w-[190px]",
      )}
    >
      <div className={cn("flex items-center gap-2 px-3 pt-4 pb-3", mini && "justify-center px-2")}>
        <div className="w-7 h-7 rounded-md bg-violet-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
          NS
        </div>
        {!mini && (
          <div className="min-w-0">
            <div className="text-sm font-semibold truncate">Nexus Simulator</div>
            <div className="text-[10px] text-muted-foreground truncate">Enterprise data replicas</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
        {MENU.map((section) => (
          <div key={section.label}>
            {!mini && (
              <div className="px-2 mb-1 text-[10px] font-semibold tracking-wider text-muted-foreground">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = active(item.path);
                return (
                  <button
                    key={item.id}
                    onClick={() => nav(item.path)}
                    className={cn(
                      "w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
                      isActive
                        ? "bg-violet-600/15 text-violet-700 dark:text-violet-300"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-800",
                      mini && "justify-center px-0",
                    )}
                    title={item.name}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {!mini && <span className="truncate">{item.name}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="p-2 border-t border-slate-200 dark:border-[#1e2740]">
        <button
          onClick={() => nav("/settings")}
          className={cn(
            "w-full flex items-center gap-2 rounded-md px-2 py-2 text-sm",
            active("/settings")
              ? "bg-violet-600/15 text-violet-700 dark:text-violet-300"
              : "text-slate-600 dark:text-slate-300 hover:bg-slate-200/70 dark:hover:bg-slate-800",
            mini && "justify-center px-0",
          )}
        >
          <Settings className="h-4 w-4" />
          {!mini && <span>Settings</span>}
        </button>
        <button
          onClick={() => setMini((v) => !v)}
          className="mt-1 w-full flex items-center justify-center rounded-md py-1 text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className={cn("h-4 w-4 transition-transform", mini && "rotate-180")} />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
