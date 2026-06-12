// App shell: dark navy sidebar + light content area, responsive (collapsible
// sidebar on mobile), top bar with notification bell and last-sync time.
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Bell, Briefcase, FileText, FlaskConical, LayoutDashboard, LogOut, Menu,
  Search, Settings, ShieldCheck, Tags, X,
} from 'lucide-react'
import { api, fmtDateTime } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Logo from './Logo'
import { Badge, cn } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/my-tenders', label: 'My Tenders', icon: Briefcase },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/keywords', label: 'Keywords', icon: Tags },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [stats, setStats] = useState(null)
  const [config, setConfig] = useState(null)
  const [disclaimerDismissed, setDisclaimerDismissed] = useState(
    () => sessionStorage.getItem('tr_disclaimer') === '1',
  )

  useEffect(() => {
    api.get('/dashboard/stats').then(setStats).catch(() => {})
    api.get('/config', undefined, { auth: false }).then(setConfig).catch(() => {})
  }, [])

  const initial = (user?.company_name || user?.email || '?').charAt(0).toUpperCase()

  const nav = (
    <nav className="flex-1 space-y-1 px-3">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => setSidebarOpen(false)}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
              isActive ? 'bg-teal/15 text-teal-light' : 'text-slate-400 hover:bg-white/5 hover:text-white',
            )
          }
        >
          <Icon className="h-4.5 w-4.5" />
          {label}
        </NavLink>
      ))}
      {user?.role === 'superadmin' && (
        <NavLink
          to="/admin"
          onClick={() => setSidebarOpen(false)}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
              isActive ? 'bg-teal/15 text-teal-light' : 'text-slate-400 hover:bg-white/5 hover:text-white',
            )
          }
        >
          <ShieldCheck className="h-4.5 w-4.5" />
          Admin
        </NavLink>
      )}
    </nav>
  )

  return (
    <div className="flex h-full">
      {/* Sidebar — desktop */}
      <aside className="hidden w-60 shrink-0 flex-col bg-navy lg:flex">
        <div className="px-5 py-5"><Logo /></div>
        {nav}
        <div className="border-t border-white/10 p-4">
          <Badge color={user?.tier === 'pro' ? 'teal' : 'slate'} className="mb-2">
            {user?.tier === 'pro' ? '⭐ PRO PLAN' : 'FREE PLAN'}
          </Badge>
          <p className="truncate text-xs text-slate-500">{user?.email}</p>
        </div>
      </aside>

      {/* Sidebar — mobile drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-navy/60" onClick={() => setSidebarOpen(false)} />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col bg-navy">
            <div className="flex items-center justify-between px-5 py-5">
              <Logo />
              <button onClick={() => setSidebarOpen(false)} className="text-slate-400"><X className="h-5 w-5" /></button>
            </div>
            {nav}
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2.5 lg:px-6">
          <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setSidebarOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-xs text-slate-400 sm:block">
            Last sync: <span className="font-medium text-slate-600">{stats?.last_sync ? fmtDateTime(stats.last_sync) : 'never'}</span>
          </div>
          <div className="flex-1" />
          <button
            onClick={() => navigate('/alerts')}
            className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 cursor-pointer"
            title="New tenders since your last login"
          >
            <Bell className="h-5 w-5" />
            {stats?.new_since_last_login > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-teal px-1 text-[10px] font-bold text-white">
                {stats.new_since_last_login > 99 ? '99+' : stats.new_since_last_login}
              </span>
            )}
          </button>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy text-sm font-bold text-white">
              {initial}
            </div>
            <div className="hidden sm:block">
              <p className="max-w-44 truncate text-xs font-semibold text-navy">{user?.company_name || user?.email}</p>
              <p className="text-[10px] text-slate-400">{user?.state || 'India'}</p>
            </div>
            <button onClick={() => { logout(); navigate('/login') }} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-red-600 cursor-pointer" title="Logout">
              <LogOut className="h-4.5 w-4.5" />
            </button>
          </div>
        </header>

        {/* Data-source banner — demo data must never be mistaken for real */}
        {config?.demo_mode && (
          <div className="flex items-center gap-2 bg-orange-100 px-4 py-2 text-[11px] font-medium text-orange-900 lg:px-6">
            <FlaskConical className="h-4 w-4 shrink-0" />
            <span>
              <b>DEMO DATA</b> — these are realistic <b>sample</b> tenders, not live listings,
              so they won't appear on the official portals. To pull real tenders, set
              <code className="mx-1 rounded bg-orange-200 px-1">DEMO_MODE=false</code> in your
              <code className="mx-1 rounded bg-orange-200 px-1">.env</code> and restart — scraping is
              free (Scrapling engine), no API key needed.
            </span>
          </div>
        )}
        {config && !config.demo_mode && config.stealth_browser_ready === false && (
          <div className="flex items-center gap-2 bg-sky-50 px-4 py-2 text-[11px] text-sky-800 lg:px-6">
            <FlaskConical className="h-4 w-4 shrink-0" />
            <span>
              <b>Live mode.</b> NIC portals (CPPP, eTenders, TN, AP, MH, UP, DL, KL) are active.
              The stealth browser isn't installed, so <b>GeM and JS-heavy portals are skipped</b> —
              enable it with <code className="mx-1 rounded bg-sky-100 px-1">scrapling install</code> (local)
              or <code className="mx-1 rounded bg-sky-100 px-1">INSTALL_BROWSER=true</code> + rebuild (Docker).
            </span>
          </div>
        )}

        {/* Disclaimer banner */}
        {!disclaimerDismissed && (
          <div className="flex items-center justify-between gap-3 bg-amber-50 px-4 py-2 text-[11px] text-amber-800 lg:px-6">
            <span>
              ⚠️ This app aggregates publicly available tender information. <b>Always verify on the official portal before bidding.</b>
            </span>
            <button
              onClick={() => { sessionStorage.setItem('tr_disclaimer', '1'); setDisclaimerDismissed(true) }}
              className="shrink-0 font-semibold underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>

        <footer className="border-t border-slate-200 bg-white px-6 py-2 text-center text-[10px] text-slate-400">
          Powered by TenderRadar · Tender data aggregated from public government portals — verify before bidding · All times IST
        </footer>
      </div>
    </div>
  )
}
