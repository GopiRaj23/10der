// "My Tenders": keyword-matched feed, watchlist and pipeline status views.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import TenderTable from '../components/TenderTable'
import { Card, Pagination, Tabs } from '../components/ui'

const TABS = [
  { value: 'matched', label: 'Matched to my keywords' },
  { value: 'watchlist', label: 'Watchlist' },
  { value: 'interested', label: 'Interested' },
  { value: 'bidding', label: 'Bidding' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

export default function MyTenders() {
  const [tab, setTab] = useState('matched')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  const load = useCallback(async (pageNum = 1, activeTab = tab) => {
    setLoading(true)
    try {
      if (activeTab === 'watchlist') {
        const items = await api.get('/tenders/bookmarks')
        setData({ items, total: items.length, page: 1, page_size: items.length || 1 })
      } else {
        const params = { page: pageNum, page_size: 20, sort: 'closing' }
        if (activeTab === 'matched') params.mine = true
        else params.status = activeTab
        const res = await api.get('/tenders', params)
        setData(res)
      }
      setPage(pageNum)
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => { load(1, tab) }, [tab])

  const updateRow = (updated) => {
    // A row may leave the current view when its status/bookmark changes
    if (tab === 'watchlist' && !updated.bookmarked) {
      setData((d) => ({ ...d, items: d.items.filter((t) => t.id !== updated.id) }))
    } else if (['interested', 'bidding', 'won', 'lost'].includes(tab) && updated.user_status !== tab) {
      setData((d) => ({ ...d, items: d.items.filter((t) => t.id !== updated.id) }))
    } else {
      setData((d) => ({ ...d, items: d.items.map((t) => (t.id === updated.id ? updated : t)) }))
    }
  }

  const emptyByTab = {
    matched: ['No matches yet', 'Add keywords and run a sync — matching tenders will appear here automatically.'],
    watchlist: ['Your watchlist is empty', 'Bookmark tenders with the ⭐ icon to track them here.'],
    interested: ['Nothing marked Interested', 'Use the status dropdown on any tender to build your pipeline.'],
    bidding: ['No active bids', 'Mark tenders as "Bidding" when you submit a bid.'],
    won: ['No wins recorded yet', 'Fingers crossed — mark results as they come in.'],
    lost: ['No losses recorded', 'Track lost bids to analyse win rates.'],
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">My Tenders</h1>
        <p className="text-xs text-slate-500">Tenders matched to your keywords plus your tracked pipeline</p>
      </div>
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      <Card>
        <TenderTable
          items={data?.items}
          loading={loading}
          onUpdated={updateRow}
          emptyTitle={emptyByTab[tab][0]}
          emptyMessage={emptyByTab[tab][1]}
        />
        {data && tab !== 'watchlist' && (
          <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={(p) => load(p)} />
        )}
      </Card>
    </div>
  )
}
