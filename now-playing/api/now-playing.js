// Vercel function: GET /api/now-playing?theme=dark|light
// Returns the "Now playing" card as an SVG, built fresh on every request.
//
// Needs three environment variables on the Vercel project:
//   SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
// (get the refresh token once with scripts/get-refresh-token.mjs)

import { renderCard } from "../lib/card.js";

const TOKEN_URL = "https://accounts.spotify.com/api/token";
const API = "https://api.spotify.com/v1/me/player";

async function accessToken() {
  const { SPOTIFY_CLIENT_ID: id, SPOTIFY_CLIENT_SECRET: secret, SPOTIFY_REFRESH_TOKEN: refresh } = process.env;
  if (!id || !secret || !refresh) throw new Error("Spotify credentials are not set on this deployment.");
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      Authorization: "Basic " + Buffer.from(`${id}:${secret}`).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: refresh }),
  });
  if (!res.ok) throw new Error(`Spotify token refresh failed (${res.status}).`);
  return (await res.json()).access_token;
}

// GitHub shows README images through its own proxy, which can't load images from
// other sites inside an SVG, so the album art is embedded as a data: URI.
async function inlineImage(url) {
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const type = res.headers.get("content-type") || "image/jpeg";
    return `data:${type};base64,${Buffer.from(await res.arrayBuffer()).toString("base64")}`;
  } catch {
    return null;
  }
}

function smallestCover(images = []) {
  // Spotify lists 640, 300 and 64 px covers; 300 stays sharp at 106 px on retina screens.
  const pick = images.find((i) => i.width === 300) ?? images[images.length - 1] ?? images[0];
  return pick?.url;
}

async function currentTrack(token) {
  const headers = { Authorization: `Bearer ${token}` };
  const now = await fetch(`${API}/currently-playing?additional_types=track,episode`, { headers });
  if (now.status === 200) {
    const d = await now.json();
    const item = d.item;
    if (item) {
      const isEpisode = item.type === "episode";
      return {
        title: item.name,
        artist: isEpisode ? item.show?.name : item.artists.map((a) => a.name).join(", "),
        album: isEpisode ? "Podcast" : item.album?.name,
        coverUrl: smallestCover(isEpisode ? item.images : item.album?.images),
        url: item.external_urls?.spotify,
        playing: !!d.is_playing,
        progressMs: d.progress_ms ?? 0,
        durationMs: item.duration_ms ?? 0,
      };
    }
  }
  const recent = await fetch(`${API}/recently-played?limit=1`, { headers });
  if (!recent.ok) return null;
  const item = (await recent.json()).items?.[0]?.track;
  if (!item) return null;
  return {
    title: item.name,
    artist: item.artists.map((a) => a.name).join(", "),
    album: item.album?.name,
    coverUrl: smallestCover(item.album?.images),
    url: item.external_urls?.spotify,
    playing: false,
    progressMs: 0,
    durationMs: item.duration_ms ?? 0,
  };
}

export default async function handler(req, res) {
  const theme = req.query?.theme === "light" ? "light" : "dark";
  let svg;
  try {
    const track = await currentTrack(await accessToken());
    if (track) track.cover = await inlineImage(track.coverUrl);
    svg = renderCard(track, theme);
  } catch (err) {
    console.error(err);
    svg = renderCard(null, theme);
  }
  res.setHeader("Content-Type", "image/svg+xml; charset=utf-8");
  // Short cache so GitHub's image proxy asks again often and the card stays current.
  res.setHeader("Cache-Control", "public, max-age=0, s-maxage=10, stale-while-revalidate=20");
  res.status(200).send(svg);
}
