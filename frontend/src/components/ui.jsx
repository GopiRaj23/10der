// Shared UI primitives (shadcn-style, hand-rolled for Tailwind v4).
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

export function cn(...parts) {
  return parts.filter(Boolean).join(' ')
}

// ---- Button ----------------------------------------------------------------
const buttonVariants = {
  primary: 'bg-teal text-white hover:bg-teal-dark shadow-sm',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50',
  ghost: 'text-slate-600 hover:bg-slate-200/70',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  navy: 'bg-navy text-white hover:bg-navy-light',
}

export function Button({ variant = 'primary', size = 'md', className, disabled, ...props }) {
  const sizes = { sm: 'px-2.5 py-1.5 text-xs', md: 'px-4 py-2 text-sm', lg: 'px-5 py-2.5 text-base' }
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-teal/50 cursor-pointer',
        disabled && 'opacity-50 pointer-events-none',
        buttonVariants[variant], sizes[size], className,
      )}
      disabled={disabled}
      {...props}
    />
  )
}

// ---- Form controls -----------------------------------------------------------
export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm',
        'placeholder:text-slate-400 focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/30',
        className,
      )}
      {...props}
    />
  )
}

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm',
        'placeholder:text-slate-400 focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/30',
        className,
      )}
      {...props}
    />
  )
}

export function Select({ className, children, ...props }) {
  return (
    <select
      className={cn(
        'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm',
        'focus:border-teal focus:outline-none focus:ring-2 focus:ring-teal/30',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export function Label({ className, children, ...props }) {
  return (
    <label className={cn('mb-1 block text-xs font-semibold text-slate-600', className)} {...props}>
      {children}
    </label>
  )
}

export function Switch({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative h-6 w-11 rounded-full transition-colors cursor-pointer',
        checked ? 'bg-teal' : 'bg-slate-300',
        disabled && 'opacity-50 pointer-events-none',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

// ---- Card / Badge ----------------------------------------------------------------
export function Card({ className, children }) {
  return (
    <div className={cn('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
      <div>
        <h3 className="text-sm font-semibold text-navy">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Badge({ color = 'slate', className, children }) {
  const colors = {
    slate: 'bg-slate-100 text-slate-700',
    teal: 'bg-teal/10 text-teal-dark',
    green: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    red: 'bg-red-100 text-red-700',
    navy: 'bg-navy text-white',
    purple: 'bg-purple-100 text-purple-700',
  }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold', colors[color], className)}>
      {children}
    </span>
  )
}

export function RelevanceBadge({ score }) {
  if (score === null || score === undefined) return <span className="text-xs text-slate-400">—</span>
  const band = score >= 70 ? 'green' : score >= 40 ? 'amber' : 'red'
  const dot = score >= 70 ? '🟢' : score >= 40 ? '🟡' : '🔴'
  return <Badge color={band}>{dot} {Math.round(score)}</Badge>
}

// ---- Skeleton / Empty states ---------------------------------------------------
export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-200', className)} />
}

export function TableSkeleton({ rows = 6 }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-9 flex-1" />
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-20" />
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ icon: Icon = Info, title, message, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-teal/10">
        <Icon className="h-7 w-7 text-teal" />
      </div>
      <h3 className="text-sm font-semibold text-navy">{title}</h3>
      {message && <p className="mt-1 max-w-sm text-xs text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Spinner({ className }) {
  return (
    <div className={cn('h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-teal', className)} />
  )
}

// ---- Modal -------------------------------------------------------------------------
export function Modal({ open, onClose, title, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/50 p-4" onClick={onClose}>
      <div
        className={cn('max-h-[88vh] w-full overflow-y-auto rounded-xl bg-white shadow-2xl', wide ? 'max-w-2xl' : 'max-w-md')}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
          <h3 className="text-sm font-semibold text-navy">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100 cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

// ---- Tabs ----------------------------------------------------------------------------
export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg bg-slate-200/60 p-1">
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            'whitespace-nowrap rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors cursor-pointer',
            active === t.value ? 'bg-white text-navy shadow-sm' : 'text-slate-600 hover:text-navy',
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 text-[10px] text-slate-400">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

// ---- Pagination -----------------------------------------------------------------------
export function Pagination({ page, pageSize, total, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
      <span>
        Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
      </span>
      <div className="flex gap-1.5">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <span className="px-2 py-1.5 font-medium text-navy">{page} / {pages}</span>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  )
}

// ---- Toasts ------------------------------------------------------------------------------
const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const toast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])

  const icons = { success: CheckCircle2, error: AlertTriangle, info: Info }
  const colors = { success: 'border-emerald-300 text-emerald-800', error: 'border-red-300 text-red-800', info: 'border-sky-300 text-sky-800' }

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((t) => {
          const Icon = icons[t.type] || Info
          return (
            <div key={t.id} className={cn('pointer-events-auto flex items-start gap-2 rounded-lg border bg-white px-3.5 py-2.5 text-xs font-medium shadow-lg', colors[t.type])}>
              <Icon className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{t.message}</span>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
