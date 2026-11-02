// Keeps the Spotify tokens alive without anyone re-running the sign-in script.
//
// Spotify refresh tokens expire after 180 days, but when we use one Spotify may
// hand back a new one. The newest refresh token (and the current 1-hour access
// token) is saved in a private Vercel Blob file, so the card keeps renewing
// itself as long as it gets used now and then.
//
// Alongside the tokens the file records when the current refresh token was
// issued and whether the last refresh failed, so tokenStatus() can warn before
// the 180 days run out (see api/token-status.js and the README workflow).
//
// Reads go: memory (same warm function) -> private blob -> SPOTIFY_REFRESH_TOKEN env.
// The env value is only the starting point from the first sign-in.

import { createHash } from "node:crypto";
import { get, put } from "@vercel/blob";

const TOKEN_URL = "https://accounts.spotify.com/api/token";
const FILE = "spotify/tokens.json";
const EARLY = 60_000; // refresh a minute before the access token runs out
export const LIFETIME_DAYS = 180;
const DAY = 86_400_000;

let memory = null; // { refreshToken, accessToken, expiresAt, issuedAt, seed, lastError, lastErrorAt }

// A short fingerprint of SPOTIFY_REFRESH_TOKEN. When it changes, you signed in
// again, so the new token wins over the saved one.
const seed = () =>
  process.env.SPOTIFY_REFRESH_TOKEN
    ? createHash("sha256").update(process.env.SPOTIFY_REFRESH_TOKEN).digest("hex").slice(0, 16)
    : null;

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
  if (fresh(memory) && memory.seed === seed()) return memory.accessToken;

  const stored = await readStored();
  const resignedIn = !!stored && stored.seed !== seed();
  if (fresh(stored) && !resignedIn) {
    if (!stored.issuedAt) {
      // Files saved before issue dates were tracked: the token is from the first sign-in.
      stored.issuedAt = Date.now();
      stored.seed = seed();
      await save(stored);
    }
    memory = stored;
    return stored.accessToken;
  }

  // Normally the newest saved refresh token goes first, then the one from the sign-in.
  // Right after a new sign-in, the new one goes first.
  const order = resignedIn
    ? [process.env.SPOTIFY_REFRESH_TOKEN, stored?.refreshToken]
    : [stored?.refreshToken, process.env.SPOTIFY_REFRESH_TOKEN];
  const candidates = [...new Set(order.filter(Boolean))];
  if (!candidates.length) throw new Error("No Spotify refresh token is set.");

  let lastError;
  for (const candidate of candidates) {
    try {
      const next = await refresh(candidate);
      if (next.refreshToken !== candidate) {
        next.issuedAt = Date.now();
        console.log("Spotify issued a new refresh token; saved it.");
      } else if (candidate === stored?.refreshToken && stored.issuedAt) {
        next.issuedAt = stored.issuedAt;
      } else {
        next.issuedAt = Date.now();
      }
      next.seed = seed();
      memory = next;
      await save(next);
      return next.accessToken;
    } catch (err) {
      lastError = err;
    }
  }
  if (stored) await save({ ...stored, lastError: lastError.message, lastErrorAt: Date.now() });
  throw lastError;
}

/**
 * How long the current refresh token has left, for the expiry warning.
 * Never includes any token, only dates and whether Spotify is refusing it.
 */
export async function tokenStatus() {
  const stored = await readStored();
  if (!stored?.issuedAt) return { known: false, failing: false };
  const expiresAt = stored.issuedAt + LIFETIME_DAYS * DAY;
  // A failure older than the last successful save doesn't count.
  const failing = !!stored.lastErrorAt && !(stored.expiresAt > stored.lastErrorAt);
  return {
    known: true,
    issuedAt: new Date(stored.issuedAt).toISOString(),
    expiresAt: new Date(expiresAt).toISOString(),
    daysLeft: Math.floor((expiresAt - Date.now()) / DAY),
    failing,
    lastError: failing ? stored.lastError : undefined,
  };
}
