const shared = {
  width: 18,
  height: 18,
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export const navIcons = {
  Dashboard: (
    <svg {...shared}>
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.2" />
      <rect x="11.5" y="2.5" width="6" height="6" rx="1.2" />
      <rect x="2.5" y="11.5" width="6" height="6" rx="1.2" />
      <rect x="11.5" y="11.5" width="6" height="6" rx="1.2" />
    </svg>
  ),
  "Route Planner": (
    <svg {...shared}>
      <circle cx="4.5" cy="15.5" r="2" />
      <circle cx="15.5" cy="4.5" r="2" />
      <path d="M6.2 14c3-1 2-6 4.8-7s2.2-2.8 4.5-2.8" />
    </svg>
  ),
  "Live Trips": (
    <svg {...shared}>
      <path d="M10 2l6.5 15L10 13.5 3.5 17z" strokeLinejoin="round" />
    </svg>
  ),
  Incidents: (
    <svg {...shared}>
      <path d="M10 3l8 14H2z" strokeLinejoin="round" />
      <path d="M10 8v4" />
      <circle cx="10" cy="14.5" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  ),
  "Risk Map": (
    <svg {...shared}>
      <path d="M2 5l5.5-2 5 2 5-2v12l-5 2-5-2-5.5 2z" strokeLinejoin="round" />
      <path d="M7.5 3v12M12.5 5v12" />
    </svg>
  ),
  Analytics: (
    <svg {...shared}>
      <path d="M3 17V9" />
      <path d="M10 17V3" />
      <path d="M17 17v-6" />
    </svg>
  ),
  Fleet: (
    <svg {...shared}>
      <path d="M3 12.5V9l1.5-3.5h9L15 9v3.5" strokeLinejoin="round" />
      <path d="M3 12.5h12" />
      <circle cx="6" cy="14" r="1.4" />
      <circle cx="13" cy="14" r="1.4" />
    </svg>
  ),
  Settings: (
    <svg {...shared}>
      <circle cx="10" cy="10" r="2.6" />
      <path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.4 4.6l-1.4 1.4M6 12.6l-1.4 1.4M15.4 15.4l-1.4-1.4M6 7.4L4.6 6" />
    </svg>
  ),
};
