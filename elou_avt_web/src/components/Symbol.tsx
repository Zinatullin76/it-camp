interface SymbolProps {
  color: string;
  size?: number;
}

// P&ID-style equipment symbols drawn in a 64x40 viewBox.
export default function Symbol({ type, color, size = 40 }: { type: string; color: string; size?: number }) {
  const stroke = color;
  const fill = color;
  const dim = { stroke, strokeWidth: 2, fill: 'none' as const, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };

  return (
    <svg width={size} height={(size * 40) / 64} viewBox="0 0 64 40">
      {type === 'source' && (
        <>
          <circle cx="14" cy="20" r="9" {...dim} />
          <path d="M23 20 L58 20" {...dim} />
          <path d="M52 14 L58 20 L52 26" fill={fill} />
        </>
      )}
      {type === 'sink' && (
        <>
          <path d="M8 20 L58 20" {...dim} />
          <path d="M14 14 L8 20 L14 26" fill={fill} />
          <path d="M36 12 L36 28 M48 14 L48 26" {...dim} />
        </>
      )}
      {type === 'pump' && (
        <>
          <circle cx="16" cy="20" r="12" {...dim} />
          <path d="M28 20 L56 20" {...dim} />
          <path d="M50 14 L56 20 L50 26" fill={fill} />
          <path d="M16 14 L21 20 L16 26" fill={fill} />
        </>
      )}
      {type === 'valve' && (
        <>
          <path d="M8 20 L26 20 M38 20 L56 20" {...dim} />
          <path d="M26 14 L38 20 L26 26 Z" {...dim} />
        </>
      )}
      {type === 'elou' && (
        <>
          <rect x="6" y="12" width="52" height="16" rx="8" {...dim} />
          <path d="M22 12 L26 28 M30 12 L34 28 M38 12 L42 28" {...dim} />
          <path d="M0 20 L6 20 M58 20 L64 20" {...dim} />
        </>
      )}
      {type === 'heat_exchanger' && (
        <>
          <rect x="10" y="8" width="44" height="24" {...dim} />
          <path d="M6 16 L58 16 M6 24 L58 24" {...dim} />
          <path d="M18 12 L18 28 M26 12 L26 28 M34 12 L34 28 M42 12 L42 28" {...dim} opacity={0.5} />
        </>
      )}
      {type === 'heater' && (
        <>
          <circle cx="32" cy="20" r="13" {...dim} />
          <path d="M28 16 a4 4 0 0 0 0 8 a3 3 0 0 0 0-6 a2 2 0 0 0 0-4" fill={fill} opacity={0.8} />
          <path d="M10 20 L19 20 M45 20 L54 20" {...dim} />
        </>
      )}
      {type === 'column' && (
        <>
          <rect x="24" y="4" width="16" height="32" {...dim} />
          <path d="M10 20 L24 20 M40 20 L54 20" {...dim} />
          <path d="M24 8 L40 8 M24 14 L40 14 M24 20 L40 20 M24 26 L40 26 M24 32 L40 32" {...dim} opacity={0.45} />
          <path d="M54 14 L60 20 L54 26" fill={fill} />
        </>
      )}
      {type === 'separator' && (
        <>
          <rect x="18" y="6" width="28" height="28" rx="4" {...dim} />
          <path d="M22 6 L22 34 M26 6 L26 34" {...dim} opacity={0.5} />
          <path d="M4 20 L18 20 M46 20 L60 20" {...dim} />
        </>
      )}
    </svg>
  );
}
