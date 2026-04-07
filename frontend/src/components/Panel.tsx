import type { ReactNode } from 'react'

export function Panel(props: {
  title: string
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={[
        'relative overflow-hidden rounded-2xl border border-[var(--gc-panel-border)] bg-[var(--gc-panel)]',
        'backdrop-blur-md shadow-[0_0_0_1px_rgba(0,212,255,0.08),_0_14px_55px_rgba(0,0,0,0.55)]',
        props.className ?? '',
      ].join(' ')}
    >
      <div className="pointer-events-none absolute inset-0 opacity-[0.55]">
        <div className="gc-grid absolute inset-0" />
      </div>

      <header className="relative flex items-center justify-between gap-4 px-4 pt-4">
        <div className="text-xs uppercase tracking-[0.26em] text-[var(--gc-muted)]">
          {props.title}
        </div>
        {props.right ? (
          <div className="font-mono text-xs text-[var(--gc-muted)]">{props.right}</div>
        ) : null}
      </header>
      <div className="relative p-4 pt-3">{props.children}</div>
    </section>
  )
}

