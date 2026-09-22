/** Inline stroke icons. No icon font, no emoji — they inherit colour and size. */

type Props = { className?: string; size?: number };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
});

/** Wingman's mark: three linked nodes — a knowledge graph. */
export function BrainMark({ size = 24, className }: Props) {
  return (
    <svg {...base(size)} className={className}>
      <circle cx="6" cy="7" r="2.4" />
      <circle cx="18" cy="6" r="2.4" />
      <circle cx="12" cy="17" r="2.4" />
      <path d="M7.7 8.6l3 6.2M16.6 8.1l-3.3 6.9M8.3 6.6h7.3" />
    </svg>
  );
}

export function Alert({ size = 16, className }: Props) {
  return (
    <svg {...base(size)} strokeWidth={2.2} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16.2v.1" />
    </svg>
  );
}

export function Check({ size = 16, className }: Props) {
  return (
    <svg {...base(size)} strokeWidth={2.6} className={className}>
      <path d="M4 12.5l5.5 5.5L20 6.5" />
    </svg>
  );
}

export function Calendar({ size = 20, className }: Props) {
  return (
    <svg {...base(size)} className={className}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}

export function Document({ size = 20, className }: Props) {
  return (
    <svg {...base(size)} className={className}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  );
}

export function Search({ size = 20, className }: Props) {
  return (
    <svg {...base(size)} className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="M16.5 16.5L21 21" />
    </svg>
  );
}

export function Gear({ size = 20, className }: Props) {
  return (
    <svg {...base(size)} className={className}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19.4 14.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.03 1.56V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 8.4 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.03H2a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 3.7 8.4a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H8.4A1.7 1.7 0 0 0 9.43 2.5V2a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.07a1.7 1.7 0 0 0 1.56 1.03H22a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.56 1.03z" />
    </svg>
  );
}

export function ArrowLeft({ size = 18, className }: Props) {
  return (
    <svg {...base(size)} strokeWidth={2} className={className}>
      <path d="M19 12H5M11 18l-6-6 6-6" />
    </svg>
  );
}
