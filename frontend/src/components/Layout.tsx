import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useMyStats } from "../hooks/queries/useUsers";
import ErrorBoundary from "./ErrorBoundary";

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  end?: boolean;
}

function NavItem({ to, icon, label, end }: Readonly<NavItemProps>) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-4 py-2 text-sm rounded-md mx-2 transition-colors ${
          isActive
            ? "bg-gray-100 text-gray-900 font-medium"
            : "text-gray-500 hover:text-gray-700 hover:bg-gray-50"
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { data: stats } = useMyStats();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="flex h-full bg-gray-50">
      <div className="w-52 bg-white border-r border-gray-100 flex flex-col flex-shrink-0">
        <div className="px-4 pt-5 pb-5 flex items-center gap-2.5">
          <svg
            width="24"
            height="24"
            viewBox="0 0 32 32"
            xmlns="http://www.w3.org/2000/svg"
            className="flex-shrink-0"
          >
            <rect width="32" height="32" rx="7" fill="#ffffff" />
            <circle cx="16" cy="16" r="5.5" fill="#3b82f6" />
            <line x1="16" y1="10.5" x2="16" y2="4" stroke="#3b82f6" strokeWidth="1" opacity="0.4" />
            <line
              x1="20.8"
              y1="13"
              x2="26"
              y2="9.5"
              stroke="#3b82f6"
              strokeWidth="1"
              opacity="0.3"
            />
            <line x1="21" y1="19" x2="27" y2="22" stroke="#ef4444" strokeWidth="1" opacity="0.35" />
            <line
              x1="16"
              y1="21.5"
              x2="15"
              y2="28"
              stroke="#f59e0b"
              strokeWidth="1"
              opacity="0.35"
            />
            <line
              x1="11.2"
              y1="19"
              x2="6"
              y2="22.5"
              stroke="#f59e0b"
              strokeWidth="1"
              opacity="0.3"
            />
            <line
              x1="11"
              y1="13"
              x2="5.5"
              y2="9.5"
              stroke="#a855f7"
              strokeWidth="1"
              opacity="0.35"
            />
            <circle cx="16" cy="3" r="2.5" fill="#3b82f6" />
            <circle cx="27.5" cy="8.5" r="2" fill="#3b82f6" opacity="0.7" />
            <circle cx="28" cy="23" r="3" fill="#ef4444" />
            <circle cx="15" cy="29" r="2.5" fill="#f59e0b" />
            <circle cx="4.5" cy="23.5" r="2" fill="#f59e0b" opacity="0.7" />
            <circle cx="4" cy="8.5" r="2.5" fill="#a855f7" />
          </svg>
          <span className="text-sm font-medium text-gray-900 tracking-tight">
            meta<span className="text-blue-500">-vis</span>
          </span>
        </div>

        <nav className="flex flex-col gap-0.5 flex-1">
          <NavItem
            to="/cases"
            label="Cases"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <rect
                  x="1"
                  y="2"
                  width="14"
                  height="12"
                  rx="1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
                <path
                  d="M4 6h8M4 9h5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
                <path
                  d="M6 2v2M10 2v2"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
            }
          />
          <NavItem
            to="/samples"
            label="All samples"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <rect
                  x="1"
                  y="1"
                  width="6"
                  height="6"
                  rx="1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
                <rect
                  x="9"
                  y="1"
                  width="6"
                  height="6"
                  rx="1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
                <rect
                  x="1"
                  y="9"
                  width="6"
                  height="6"
                  rx="1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
                <rect
                  x="9"
                  y="9"
                  width="6"
                  height="6"
                  rx="1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                />
              </svg>
            }
          />
          <NavItem
            to="/alerts"
            label="Outbreak alerts"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <path
                  d="M8 2L14 13H2L8 2z"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinejoin="round"
                />
                <path
                  d="M8 6v3M8 11v.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
            }
          />
          <NavItem
            to="/ntc"
            label="NTC trends"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <path
                  d="M1 12 L4 8 L7 9 L10 5 L13 6 L15 3"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="4" cy="8" r="1.2" fill="currentColor" />
                <circle cx="10" cy="5" r="1.2" fill="currentColor" />
              </svg>
            }
          />
          <NavItem
            to="/pathogens"
            label="Pathogens"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.3" />
                <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M8 2.5v1.5M8 12v1.5M2.5 8h1.5M12 8h1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
            }
          />
        </nav>

        <div className="flex flex-col border-t border-gray-100">
          <div className="px-4 py-4 flex flex-col gap-1">
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
        </div>
      </div>

      <div className="flex-1 overflow-hidden flex flex-col">
        <ErrorBoundary key={location.pathname} label="page">
          <Outlet />
        </ErrorBoundary>
      </div>
    </div>
  );
}
