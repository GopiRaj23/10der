// Shared split-screen shell for the public auth pages.
import Logo from './Logo'

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen">
      <div className="hidden flex-1 flex-col justify-between bg-navy p-10 lg:flex">
        <Logo size={40} />
        <div>
          <h1 className="max-w-md text-3xl font-bold leading-tight text-white">
            Every Indian government tender that matters to your business. <span className="text-teal">One radar.</span>
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            TenderRadar scans GeM, CPPP, NIC eProcurement, Defence, Railways and 10+ state portals
            against your business keywords — and alerts you the moment a relevant tender drops.
          </p>
          <div className="mt-6 flex flex-wrap gap-2 text-[11px] text-slate-400">
            {['GeM', 'CPPP', 'eTenders NIC', 'Defence (MoD)', 'IREPS', 'Tamil Nadu', 'Maharashtra', '+12 more'].map((p) => (
              <span key={p} className="rounded-full border border-white/15 px-2.5 py-1">{p}</span>
            ))}
          </div>
        </div>
        <p className="text-[11px] text-slate-500">
          Aggregates publicly available tender information · Always verify on the official portal before bidding
        </p>
      </div>

      <div className="flex flex-1 items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-sm">
          <div className="mb-6 lg:hidden"><Logo light={false} /></div>
          <h2 className="text-xl font-bold text-navy">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  )
}
