import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function NavItem({ to, icon, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-2.5 px-4 py-2 text-sm rounded-md mx-2 transition-colors ${
          isActive
            ? 'bg-gray-100 text-gray-900 font-medium'
            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
        }`
      }
    >
      {icon}
      {label}
    </NavLink>
  )
}

export default function Layout() {
  const { user, role, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
     <div className="flex h-full bg-gray-50">
      {/* Sidebar */}
      <div className="w-52 bg-white border-r border-gray-100 flex flex-col flex-shrink-0">
        <div className="px-4 pt-5 pb-6">
          <span className="text-sm font-medium text-gray-900 tracking-tight">meta-vis</span>
        </div>

        <nav className="flex flex-col gap-0.5 flex-1">
          <NavItem
            to="/cases"
            label="Cases"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <rect x="1" y="2" width="14" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M4 6h8M4 9h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                <path d="M6 2v2M10 2v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
            }
          />
          <NavItem
            to="/samples"
            label="All samples"
            icon={
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
              </svg>
            }
          />
        </nav>

        <div className="flex flex-col border-t border-gray-100">
          {role === 'admin' && (
            <div className="px-2 pt-2">
              <NavItem
                to="/admin"
                label="Admin"
                icon={
                  <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
                    <path d="M3 13c0-2.761 2.239-5 5-5s5 2.239 5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    <circle cx="13" cy="4" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
                    <path d="M13 6v1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                }
              />
            </div>
          )}
          <div className="px-4 py-4 flex items-center justify-between">
            <span className="text-xs text-gray-400">{user}</span>
            <button
              onClick={handleLogout}
              className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </div>
    </div>
  )
}