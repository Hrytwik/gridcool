export function Skeleton(props: { className?: string }) {
  return (
    <div
      className={[
        'animate-pulse rounded-2xl border border-[var(--gc-panel-border)] bg-black/25',
        props.className ?? '',
      ].join(' ')}
    >
      <div className="h-full w-full rounded-2xl bg-gradient-to-r from-white/5 via-white/10 to-white/5" />
    </div>
  )
}

