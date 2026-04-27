export function LoginIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 480 380"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      {/* Backdrop circle */}
      <circle cx="240" cy="200" r="160" fill="white" fillOpacity="0.06" />
      <circle cx="240" cy="200" r="120" fill="white" fillOpacity="0.08" />

      {/* Sound wave arcs (left) */}
      <g stroke="white" strokeOpacity="0.55" strokeWidth="2.5" strokeLinecap="round" fill="none">
        <path d="M120 180 Q105 200 120 220" />
        <path d="M100 165 Q78 200 100 235" strokeOpacity="0.4" />
        <path d="M80 150 Q50 200 80 250" strokeOpacity="0.25" />
      </g>
      {/* Sound wave arcs (right) */}
      <g stroke="white" strokeOpacity="0.55" strokeWidth="2.5" strokeLinecap="round" fill="none">
        <path d="M360 180 Q375 200 360 220" />
        <path d="M380 165 Q402 200 380 235" strokeOpacity="0.4" />
        <path d="M400 150 Q430 200 400 250" strokeOpacity="0.25" />
      </g>

      {/* Phone handset (centered) */}
      <g>
        <rect
          x="200"
          y="140"
          width="80"
          height="120"
          rx="22"
          fill="white"
          fillOpacity="0.95"
        />
        <rect
          x="208"
          y="148"
          width="64"
          height="92"
          rx="14"
          fill="#5750F1"
          fillOpacity="0.18"
        />
        {/* Speaker dot */}
        <circle cx="240" cy="156" r="3" fill="#5750F1" fillOpacity="0.4" />
        {/* Phone icon glyph */}
        <path
          d="M225 192c0-3 2-5 5-5h6c2 0 4 1 4 4 0 4 0 6 1 8s2 4 5 7c3 3 5 4 7 5s4 1 8 1c3 0 4 2 4 4v6c0 3-2 5-5 5-19 0-35-16-35-35z"
          fill="#5750F1"
        />
      </g>

      {/* Floating card 1 — transcript */}
      <g>
        <rect
          x="40"
          y="80"
          width="140"
          height="56"
          rx="12"
          fill="white"
          fillOpacity="0.95"
        />
        <circle cx="58" cy="108" r="10" fill="#5750F1" fillOpacity="0.18" />
        <path
          d="M54 108 a4 4 0 0 1 4 -4 a4 4 0 0 1 4 4 v4 a4 4 0 0 1 -4 4 a4 4 0 0 1 -4 -4z"
          fill="#5750F1"
        />
        <rect x="78" y="98" width="80" height="6" rx="3" fill="#9CA3AF" />
        <rect x="78" y="110" width="60" height="6" rx="3" fill="#D1D5DB" />
        <rect x="78" y="120" width="40" height="6" rx="3" fill="#D1D5DB" />
      </g>

      {/* Floating card 2 — booked appointment */}
      <g>
        <rect
          x="300"
          y="60"
          width="140"
          height="56"
          rx="12"
          fill="white"
          fillOpacity="0.95"
        />
        <circle cx="318" cy="88" r="10" fill="#22AD5C" fillOpacity="0.18" />
        <path
          d="M313 88l4 4 6-7"
          stroke="#22AD5C"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <rect x="338" y="78" width="70" height="6" rx="3" fill="#22AD5C" fillOpacity="0.7" />
        <rect x="338" y="90" width="90" height="6" rx="3" fill="#9CA3AF" />
        <rect x="338" y="100" width="50" height="6" rx="3" fill="#D1D5DB" />
      </g>

      {/* Floating card 3 — analytics */}
      <g>
        <rect
          x="60"
          y="270"
          width="140"
          height="60"
          rx="12"
          fill="white"
          fillOpacity="0.95"
        />
        <rect x="74" y="290" width="6" height="26" rx="2" fill="#5750F1" />
        <rect x="86" y="298" width="6" height="18" rx="2" fill="#5750F1" fillOpacity="0.6" />
        <rect x="98" y="284" width="6" height="32" rx="2" fill="#5750F1" />
        <rect x="110" y="294" width="6" height="22" rx="2" fill="#5750F1" fillOpacity="0.6" />
        <rect x="122" y="288" width="6" height="28" rx="2" fill="#5750F1" />
        <rect x="140" y="288" width="50" height="6" rx="3" fill="#9CA3AF" />
        <rect x="140" y="300" width="40" height="6" rx="3" fill="#D1D5DB" />
        <rect x="140" y="310" width="30" height="6" rx="3" fill="#D1D5DB" />
      </g>

      {/* Floating card 4 — caller */}
      <g>
        <rect
          x="290"
          y="280"
          width="150"
          height="56"
          rx="12"
          fill="white"
          fillOpacity="0.95"
        />
        <circle cx="312" cy="308" r="14" fill="#F59E0B" fillOpacity="0.25" />
        <text
          x="312"
          y="313"
          textAnchor="middle"
          fontSize="13"
          fontWeight="700"
          fill="#D97706"
          fontFamily="system-ui, sans-serif"
        >
          E
        </text>
        <rect x="332" y="298" width="80" height="6" rx="3" fill="#9CA3AF" />
        <rect x="332" y="310" width="60" height="6" rx="3" fill="#D1D5DB" />
      </g>

      {/* Connecting dots */}
      <g fill="white" fillOpacity="0.5">
        <circle cx="190" cy="130" r="2" />
        <circle cx="195" cy="120" r="2" />
        <circle cx="200" cy="115" r="2" />
        <circle cx="290" cy="115" r="2" />
        <circle cx="285" cy="130" r="2" />
        <circle cx="280" cy="135" r="2" />
        <circle cx="200" cy="270" r="2" />
        <circle cx="280" cy="270" r="2" />
      </g>
    </svg>
  );
}
