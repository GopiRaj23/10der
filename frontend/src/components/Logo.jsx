// TenderRadar logo — radar sweep motif.
export default function Logo({ size = 34, withText = true, light = true }) {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <svg width={size} height={size} viewBox="0 0 40 40" aria-label="TenderRadar logo">
        <circle cx="20" cy="20" r="19" fill="#0A9396" opacity="0.12" />
        <circle cx="20" cy="20" r="14" fill="none" stroke="#0A9396" strokeWidth="1.4" opacity="0.45" />
        <circle cx="20" cy="20" r="8" fill="none" stroke="#0A9396" strokeWidth="1.4" opacity="0.7" />
        <g className="radar-sweep">
          <path d="M20 20 L20 2 A18 18 0 0 1 35.6 11 Z" fill="#0A9396" opacity="0.55" />
        </g>
        <circle cx="20" cy="20" r="2.4" fill="#0A9396" />
        <circle cx="27" cy="26" r="2" fill="#94D2BD" />
      </svg>
      {withText && (
        <span className={`text-lg font-bold tracking-tight ${light ? 'text-white' : 'text-navy'}`}>
          Tender<span className="text-teal">Radar</span>
        </span>
      )}
    </div>
  )
}
