// Keeps the Spotify tokens alive without anyone re-running the sign-in script.
//
// Spotify refresh tokens expire after 180 days, but when we use one Spotify may
// hand back a new one. The newest refresh token (and the current 1-hour access
// token) is saved in a private Vercel Blob file, so the card keeps renewing
// itself as long as it gets used now and then.
//
// Reads go: memory (same warm function) -> private blob -> SPOTIFY_REFRESH_TOKEN env.
// The env value is only the starting point from the first sign-in.

import { get, put } from "@vercel/blob";

const TOKEN_URL = "https://accounts.spotify.com/api/token";
const FILE = "spotify/tokens.json";
const EARLY = 60_000; // refresh a minute before the access token runs out

let memory = null; // { refreshToken, accessToken, expiresAt }

async function readStored() {
  try {
    const res = await get(FILE, { access: "private", useCache: false });
    if (!res || res.statusCode !== 200 || !res.stream) return null;
    return JSON.parse(await new Response(res.stream).text());
  } catch (err) {
    console.warn("Could not read saved Spotify tokens:", err.message);
    return null;
  }
}

async function save(tokens) {
  try {
    await put(FILE, JSON.stringify(tokens), {
      access: "private",
      allowOverwrite: true,
      addRandomSuffix: false,
      contentType: "application/json",
    });
  } catch (err) {
    // The card still works this time; the next refresh tries to save again.
    console.error("Could not save Spotify tokens:", err.message);
  }
}

async function refresh(refreshToken) {
  const { SPOTIFY_CLIENT_ID: id, SPOTIFY_CLIENT_SECRET: secret } = process.env;
  if (!id || !secret) throw new Error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are not set.");
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      Authorization: "Basic " + Buffer.from(`${id}:${secret}`).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(`Spotify token refresh failed (${res.status} ${data.error ?? ""}).`);
    err.status = res.status;
    throw err;
  }
  return {
    // Spotify only sometimes sends a new refresh token; keep the old one otherwise.
    refreshToken: data.refresh_token || refreshToken,
    accessToken: data.access_token,
    expiresAt: Date.now() + (data.expires_in ?? 3600) * 1000,
  };
}

/** Returns a valid Spotify access token, renewing and saving tokens when needed. */
export async function accessToken() {
  const fresh = (t) => t?.accessToken && t.expiresAt - EARLY > Date.now();
  if (fresh(memory)) return memory.accessToken;

  const stored = await readStored();
  if (fresh(stored)) {
    memory = stored;
    return stored.accessToken;
  }

  // Try the newest saved refresh token first, then the one from the first sign-in.
  const candidates = [...new Set([stored?.refreshToken, process.env.SPOTIFY_REFRESH_TOKEN].filter(Boolean))];
  if (!candidates.length) throw new Error("No Spotify refresh token is set.");

  let lastError;
  for (const candidate of candidates) {
    try {
      const next = await refresh(candidate);
      if (next.refreshToken !== candidate) console.log("Spotify issued a new refresh token; saved it.");
      memory = next;
      await save(next);
      return next.accessToken;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError;
}
