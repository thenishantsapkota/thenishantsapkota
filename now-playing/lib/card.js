// Draws the "Now playing" card as an SVG, styled like the other profile cards:
// GitHub's neutrals, one green accent, no glows or gradients.
// Pure function: track data in, SVG string out.

const THEMES = {
  dark: { bg: "#0d1117", border: "#30363d", text: "#e6edf3", muted: "#8b949e", accent: "#3fb950", empty: "#161b22" },
  light: { bg: "#ffffff", border: "#d0d7de", text: "#1f2328", muted: "#59636e", accent: "#1a7f37", empty: "#f6f8fa" },
};

const FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Noto Sans', Helvetica, Arial, sans-serif";
const MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace";
// Spotify mark from Simple Icons (CC0), 24-unit grid.
const SPOTIFY_PATH = "M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z";

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// An SVG inside an <img> can't measure text, so long strings are trimmed by length.
const fit = (s, max) => (s.length > max ? s.slice(0, max - 1).trimEnd() + "…" : s);

const clock = (ms) => {
  const t = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
};

/**
 * @param {object|null} track  {title, artist, album, cover (data: URI or null), playing, durationMs}
 * @param {"dark"|"light"} themeName
 */
export function renderCard(track, themeName = "dark") {
  const t = THEMES[themeName] ?? THEMES.dark;
  const W = 840;
  const H = 120;
  const art = 80;
  const ax = 20;
  const ay = (H - art) / 2;
  const tx = ax + art + 20;
  const logo = `<g transform="translate(${W - 40} 20)"><path d="${SPOTIFY_PATH}" fill="${t.muted}" transform="scale(.8333)"/></g>`;

  if (!track) {
    return wrap(W, H, t, "Spotify: nothing played yet", `
  <rect x="${ax}" y="${ay}" width="${art}" height="${art}" rx="6" fill="${t.empty}" stroke="${t.border}"/>
  <text x="${tx}" y="${H / 2 + 5}" class="artist">Nothing on Spotify right now.</text>
  ${logo}`);
  }

  const playing = !!track.playing;
  // Three bars that rise and fall only while music is actually playing.
  const eq = playing
    ? [0, 1, 2]
        .map((i) => `<rect class="eq eq${i}" x="${tx + i * 5}" y="30" width="3" height="11" rx="1" fill="${t.accent}"/>`)
        .join("")
    : "";
  const status = playing ? "Listening now" : "Last played";
  const statusX = playing ? tx + 22 : tx;

  const cover = track.cover
    ? `<image href="${track.cover}" x="${ax}" y="${ay}" width="${art}" height="${art}" clip-path="url(#art)" preserveAspectRatio="xMidYMid slice"/>`
    : `<rect x="${ax}" y="${ay}" width="${art}" height="${art}" fill="${t.empty}"/>`;

  const body = `
  <defs><clipPath id="art"><rect x="${ax}" y="${ay}" width="${art}" height="${art}" rx="6"/></clipPath></defs>
  ${cover}
  <rect x="${ax}" y="${ay}" width="${art}" height="${art}" rx="6" fill="none" stroke="${t.border}"/>
  ${eq}
  <text x="${statusX}" y="41" class="status">${status}</text>
  <text x="${tx}" y="70" class="title">${esc(fit(track.title, 52))}</text>
  <text x="${tx}" y="92" class="artist">${esc(fit(track.artist, 56))}${track.album ? `<tspan class="album">, ${esc(fit(track.album, 40))}</tspan>` : ""}</text>
  <text x="${W - 20}" y="92" class="time" text-anchor="end">${clock(track.durationMs)}</text>
  ${logo}`;

  return wrap(W, H, t, `${status}: ${track.title} by ${track.artist}`, body);
}

function wrap(W, H, t, title, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">
  <title>${esc(title)}</title>
  <style>
    text { font-family: ${FONT}; }
    .status { font-size: 12px; fill: ${t.muted}; }
    .title { font-size: 19px; font-weight: 600; fill: ${t.text}; }
    .artist { font-size: 14px; fill: ${t.text}; }
    .album { fill: ${t.muted}; }
    .time { font-size: 12px; fill: ${t.muted}; font-family: ${MONO}; }
    .eq { transform-box: fill-box; transform-origin: 50% 100%; }
    @media (prefers-reduced-motion: no-preference) {
      .eq0 { animation: lvl 1s ease-in-out infinite; }
      .eq1 { animation: lvl 1s ease-in-out -.35s infinite; }
      .eq2 { animation: lvl 1s ease-in-out -.7s infinite; }
      @keyframes lvl { 0%, 100% { transform: scaleY(.4); } 50% { transform: scaleY(1); } }
    }
  </style>
  <rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="6" fill="${t.bg}" stroke="${t.border}"/>
${body}
</svg>
`;
}
