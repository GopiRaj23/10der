// Alerts: notification inbox + digest/instant-alert preferences.
import { useEffect, useState } from 'react'
import { Bell, BellRing, Mail, MessageCircle } from 'lucide-react'
import { api, fmtDateTime } from '../api/client'
import {
  Badge, Button, Card, CardHeader, cn, EmptyState, Select, Switch,
  TableSkeleton, useToast,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function Alerts() {
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const [notifications, setNotifications] = useState(null)
  const [prefs, setPrefs] = useState(null)

  useEffect(() => {
    api.get('/users/me/notifications').then(setNotifications).catch((e) => toast(e.message, 'error'))
  }, [])

  useEffect(() => {
    if (user) {
      setPrefs({
        digest_hour_ist: user.digest_hour_ist,
        instant_alerts_enabled: user.instant_alerts_enabled,
      })
    }
  }, [user])

  const savePrefs = async (patch) => {
    try {
      await api.put('/users/me', patch)
      await refreshUser()
      toast('Alert preferences saved')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const markAllRead = async () => {
    await api.post('/users/me/notifications/read-all')
    setNotifications((n) => n.map((x) => ({ ...x, is_read: true })))
    toast('All notifications marked read')
  }

  const markRead = async (n) => {
    if (n.is_read) return
    await api.post(`/users/me/notifications/${n.id}/read`)
    setNotifications((list) => list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
  }

  const typeBadge = { instant: ['red', '⚡ Instant'], digest: ['teal', '📡 Digest'], system: ['slate', 'System'] }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Alerts</h1>
        <p className="text-xs text-slate-500">Daily digests, instant high-relevance alerts and delivery channels</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Alert preferences" />
          <div className="space-y-5 p-5">
            <div>
              <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                <Mail className="h-3.5 w-3.5 text-teal" /> Daily email digest
              </p>
              <p className="mb-2 text-[11px] text-slate-400">Top 10 new matching tenders, every day at:</p>
              <Select
                value={prefs?.digest_hour_ist ?? 7}
                onChange={(e) => { const v = Number(e.target.value); setPrefs((p) => ({ ...p, digest_hour_ist: v })); savePrefs({ digest_hour_ist: v }) }}
              >
                {Array.from({ length: 24 }, (_, h) => (
                  <option key={h} value={h}>
                    {((h % 12) || 12)}:00 {h < 12 ? 'AM' : 'PM'} IST
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex items-start justify-between gap-3 border-t border-slate-100 pt-4">
              <div>
                <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                  <BellRing className="h-3.5 w-3.5 text-teal" /> Instant alerts
                </p>
                <p className="mt-0.5 text-[11px] text-slate-400">
                  Email me immediately when a tender scores above 80 relevance.
                </p>
              </div>
              <Switch
                checked={!!prefs?.instant_alerts_enabled}
                onChange={(v) => { setPrefs((p) => ({ ...p, instant_alerts_enabled: v })); savePrefs({ instant_alerts_enabled: v }) }}
              />
            </div>

            <div className="flex items-start justify-between gap-3 border-t border-slate-100 pt-4 opacity-60">
              <div>
                <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                  <MessageCircle className="h-3.5 w-3.5 text-emerald-600" /> WhatsApp alerts
                  <Badge color="amber">Coming soon</Badge>
                </p>
                <p className="mt-0.5 text-[11px] text-slate-400">Instant alerts on WhatsApp via the Business API.</p>
              </div>
              <Switch checked={false} onChange={() => {}} disabled />
            </div>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Notification history"
            action={notifications?.some((n) => !n.is_read) && (
              <Button variant="ghost" size="sm" onClick={markAllRead}>Mark all read</Button>
            )}
          />
          {!notifications ? (
            <TableSkeleton rows={5} />
          ) : notifications.length === 0 ? (
            <EmptyState icon={Bell} title="No notifications yet"
              message="Once a scrape finds tenders matching your keywords, alerts and digests will appear here." />
          ) : (
            <div className="max-h-130 divide-y divide-slate-100 overflow-y-auto">
              {notifications.map((n) => {
                const [color, label] = typeBadge[n.type] || typeBadge.system
                return (
                  <button key={n.id} onClick={() => markRead(n)}
                    className={cn('block w-full px-5 py-3 text-left transition-colors hover:bg-slate-50 cursor-pointer', !n.is_read && 'bg-teal/4')}>
                    <div className="flex items-center gap-2">
                      <Badge color={color}>{label}</Badge>
                      {!n.is_read && <span className="h-1.5 w-1.5 rounded-full bg-teal" />}
                      <span className="ml-auto text-[10px] text-slate-400">{fmtDateTime(n.created_at)}</span>
                    </div>
                    <p className="mt-1 text-[13px] font-medium text-navy">{n.title}</p>
                    {n.body && <p className="mt-0.5 text-[11px] text-slate-500">{n.body}</p>}
                  </button>
                )
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
