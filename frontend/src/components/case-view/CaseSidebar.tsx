import { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { getMyStats } from "../../api/users";
import type { MyStats } from "../../api/types";

export type CaseSection = "overview" | "samples" | "multiqc" | "report" | "comments" | "provenance";

interface NavGroup {
  label: string | null;
  items: NavItem[];
}

interface NavItem {
  id: CaseSection;
  label: string;
  icon: IconKind;
  count?: number | null;
}

type IconKind = "list" | "vial" | "leaf" | "bars" | "doc" | "chat" | "branch";

interface CaseSidebarProps {
  active: CaseSection;
  onSelect: (s: CaseSection) => void;
  counts: Partial<Record<CaseSection, number | null>>;
  hideMultiqc?: boolean;
}

// Case-specific left navigation, replacing the app sidebar inside the case view.
// Grouped into "Analysis" (data + visualisations) and "Workflow" (review actions).
export default function CaseSidebar({
  active,
  onSelect,
  counts,
  hideMultiqc,
}: Readonly<CaseSidebarProps>) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<MyStats | null>(null);

  useEffect(() => {
    getMyStats().then(setStats).catch(() => {});
  }, []);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const groups: NavGroup[] = [
    {
      label: null,
      items: [{ id: "overview", icon: "list", label: "Overview" }],
    },
    {
      label: "Analysis",
      items: [
        { id: "samples", icon: "vial", label: "Samples", count: counts.samples ?? null },
        ...(hideMultiqc
          ? []
          : [{ id: "multiqc" as const, icon: "bars" as const, label: "MultiQC" }]),
      ],
    },
    {
      label: "Workflow",
      items: [
        { id: "report", icon: "doc", label: "Report" },
        { id: "comments", icon: "chat", label: "Comments", count: counts.comments ?? null },
        { id: "provenance", icon: "branch", label: "Provenance" },
      ],
    },
  ];

  return (
    <aside className="w-56 bg-white border-r border-gray-100 flex flex-col flex-shrink-0">
      <div className="flex-1 overflow-y-auto py-4">
        {groups.map((g) => (
          <div key={g.label ?? "root"} className="mb-3">
            {g.label && (
              <div className="px-5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                {g.label}
              </div>
            )}
            {g.items.map((item) => {
              const isActive = active === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.id)}
                  className={`w-full flex items-center gap-2.5 px-5 py-1.5 text-left transition-colors text-sm ${
                    isActive
                      ? "bg-gray-50 text-gray-900 font-medium border-l-2 border-gray-900"
                      : "text-gray-600 hover:bg-gray-50 border-l-2 border-transparent"
                  }`}
                >
                  <NavIcon kind={item.icon} active={isActive} />
                  <span className="flex-1">{item.label}</span>
                  {item.count != null && (
                    <span className="text-[10px] font-mono text-gray-400">{item.count}</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div className="px-4 py-4 border-t border-gray-100 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <NavLink
            to="/preferences"
            className="text-xs text-gray-500 font-medium hover:text-gray-700 transition-colors"
          >
            {user}
          </NavLink>
          <button
            onClick={handleLogout}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Sign out
          </button>
        </div>
        {stats && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400 italic">{stats.reviewer_title}</span>
            <span className="text-xs text-gray-300">{stats.reviews} cases reviews</span>
          </div>
        )}
      </div>
    </aside>
  );
}

interface NavIconProps {
  kind: IconKind;
  active: boolean;
}

function NavIcon({ kind, active }: Readonly<NavIconProps>) {
  const stroke = active ? "#18181b" : "#a1a1aa";
  const common = {
    width: 13,
    height: 13,
    viewBox: "0 0 16 16",
    fill: "none" as const,
    stroke,
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (kind) {
    case "list":
      return (
        <svg {...common}>
          <path d="M2 4h12M2 8h12M2 12h12" />
        </svg>
      );
    case "vial":
      return (
        <svg {...common}>
          <path d="M6 2v8a2 2 0 104 0V2M5 2h6" />
        </svg>
      );
    case "leaf":
      return (
        <svg {...common}>
          <path d="M3 13s2-7 10-10c0 0-1 9-10 10z" />
          <path d="M3 13l5-5" />
        </svg>
      );
    case "bars":
      return (
        <svg {...common}>
          <path d="M3 13V8M7 13V4M11 13V10" />
        </svg>
      );
    case "doc":
      return (
        <svg {...common}>
          <path d="M4 2h6l2 2v10H4V2z" />
          <path d="M5 7h6M5 10h4" />
        </svg>
      );
    case "chat":
      return (
        <svg {...common}>
          <path d="M3 4h10v7H7l-3 2v-2H3V4z" />
        </svg>
      );
    case "branch":
      return (
        <svg {...common}>
          <circle cx="4" cy="3" r="1.5" />
          <circle cx="4" cy="13" r="1.5" />
          <circle cx="12" cy="8" r="1.5" />
          <path d="M4 4.5v7M4 8h7" />
        </svg>
      );
  }
}
