const paths = {
  layers: "m12 3 9 5-9 5-9-5 9-5Zm-9 10 9 5 9-5M3 18l9 5 9-5",
  code: "m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 20",
  play: "m8 4 13 8-13 8V4Z",
  check: "m5 12 4 4L19 6",
  alert: "m12 3 10 18H2L12 3Zm0 6v5m0 3v.1",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  upload: "M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5",
  table: "M3 4h18v16H3V4Zm0 5h18M8 4v16",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  dot: "M12 9v6m-3-3h6",
  clock: "M12 8v5l3 2m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
};

export default function Icon({ name, size = 18 }: { name: keyof typeof paths; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={paths[name]} />
  </svg>;
}
