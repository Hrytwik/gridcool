import { motion } from 'framer-motion'
import { useMemo } from 'react'

function charsFor(value: number) {
  // Odometer-friendly fixed format; commas act as static separators.
  const s = value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return s.split('')
}

function Digit(props: { digit: number; glow: string }) {
  const height = 44
  const y = -props.digit * height

  return (
    <div className="relative h-[44px] w-[22px] overflow-hidden rounded-lg border border-white/10 bg-black/20">
      <motion.div
        animate={{ y }}
        transition={{ type: 'spring', stiffness: 120, damping: 18 }}
        className="absolute left-0 top-0 w-full"
        style={{ textShadow: `0 0 18px ${props.glow}` }}
      >
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="flex h-[44px] items-center justify-center font-mono text-4xl">
            {i}
          </div>
        ))}
      </motion.div>
    </div>
  )
}

export function Odometer(props: { value: number; glow: string }) {
  const chars = useMemo(() => charsFor(props.value), [props.value])

  // Map each digit independently; separators (comma, dot) are static.
  return (
    <div className="flex items-end gap-1">
      {chars.map((c, idx) => {
        if (c >= '0' && c <= '9') {
          return <Digit key={idx} digit={Number(c)} glow={props.glow} />
        }
        return (
          <div key={idx} className="px-1 pb-1 font-mono text-4xl text-[rgba(215,226,255,0.75)]">
            {c}
          </div>
        )
      })}
    </div>
  )
}

