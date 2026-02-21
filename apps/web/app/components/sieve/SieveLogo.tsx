"use client";

export default function SieveLogo({
  size = 80,
  animate = false,
}: {
  size?: number;
  animate?: boolean;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 400 195"
      width={size}
      height={size * 0.4875}
      aria-label="Sieve logo"
      style={{ display: "block", margin: "auto" }}
      className={animate ? "sieve-fab-logo" : undefined}
    >
      <defs>
        <linearGradient id="sw-goldBody" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#E8C84A" />
          <stop offset="18%" stopColor="#D4A832" />
          <stop offset="40%" stopColor="#C49528" />
          <stop offset="65%" stopColor="#A87A1E" />
          <stop offset="85%" stopColor="#8B6318" />
          <stop offset="100%" stopColor="#6E4E12" />
        </linearGradient>
        <linearGradient id="sw-rimGold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#F0D860" />
          <stop offset="50%" stopColor="#C8A830" />
          <stop offset="100%" stopColor="#A08020" />
        </linearGradient>
        <linearGradient id="sw-bodySheen" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgba(255,255,255,0)" />
          <stop offset="35%" stopColor="rgba(255,255,255,0.18)" />
          <stop offset="50%" stopColor="rgba(255,255,255,0.22)" />
          <stop offset="65%" stopColor="rgba(255,255,255,0.18)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
        <radialGradient id="sw-holeSage" cx="50%" cy="45%" r="50%">
          <stop offset="0%" stopColor="#E8F3ED" />
          <stop offset="40%" stopColor="#CEE3D8" />
          <stop offset="70%" stopColor="#9DC7B1" />
          <stop offset="100%" stopColor="#6B9E80" />
        </radialGradient>
        <radialGradient id="sw-particleGold" cx="40%" cy="35%" r="55%">
          <stop offset="0%" stopColor="#F0D860" />
          <stop offset="45%" stopColor="#D4A832" />
          <stop offset="100%" stopColor="#8B6318" />
        </radialGradient>
      </defs>
      <g>
        {/* Rim */}
        <rect x="42" y="28" width="316" height="16" rx="3" fill="url(#sw-rimGold)" />
        <rect x="42" y="29" width="316" height="3" rx="1.5" fill="rgba(255,255,220,0.18)" />
        {/* Bowl */}
        <path
          d="M48,42 L352,42 Q350,50 346,58 Q330,88 305,102 Q270,120 200,124 Q130,120 95,102 Q70,88 54,58 Q50,50 48,42 Z"
          fill="url(#sw-goldBody)"
        />
        <path
          d="M48,42 L352,42 Q350,50 346,58 Q330,88 305,102 Q270,120 200,124 Q130,120 95,102 Q70,88 54,58 Q50,50 48,42 Z"
          fill="url(#sw-bodySheen)"
        />
        {/* Row 1 holes */}
        {[115, 149, 183, 217, 251, 285].map((cx) => (
          <g key={cx}>
            <circle cx={cx} cy={68} r={6.8} fill="url(#sw-holeSage)" />
            <circle cx={cx - 2} cy={66} r={2.3} fill="rgba(255,255,255,0.45)" />
          </g>
        ))}
        {/* Row 2 holes */}
        {[
          [132, 95],
          [166, 102],
          [200, 106],
          [234, 102],
          [268, 95],
        ].map(([cx, cy]) => (
          <g key={cx}>
            <circle cx={cx} cy={cy} r={6.4} fill="url(#sw-holeSage)" />
            <circle cx={cx! - 2} cy={cy! - 2} r={2.1} fill="rgba(255,255,255,0.42)" />
          </g>
        ))}
        {/* Particles */}
        {[
          [140, 135, 4.4],
          [170, 139, 4.6],
          [200, 142, 4.9],
          [230, 139, 4.6],
          [260, 135, 4.4],
          [160, 159, 5.7],
          [200, 167, 6.4],
          [240, 159, 5.7],
        ].map(([cx, cy, r]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill="url(#sw-particleGold)" data-particle="" />
        ))}
      </g>
    </svg>
  );
}
