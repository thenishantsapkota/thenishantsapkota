// One-time helper: signs you in to Spotify and prints the refresh token the
// card needs. Run it on your own computer:
//
//   SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=... node now-playing/scripts/get-refresh-token.mjs
//
// In your Spotify app's settings, add this Redirect URI first:
//   http://127.0.0.1:8888/callback

import http from "node:http";
import { randomBytes } from "node:crypto";

const id = process.env.SPOTIFY_CLIENT_ID;
const secret = process.env.SPOTIFY_CLIENT_SECRET;
if (!id || !secret) {
  console.error("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.");
  process.exit(1);
}

const redirect = "http://127.0.0.1:8888/callback";
const state = randomBytes(12).toString("hex");
const scope = "user-read-currently-playing user-read-recently-played";
const authUrl =
  "https://accounts.spotify.com/authorize?" +
  new URLSearchParams({ response_type: "code", client_id: id, scope, redirect_uri: redirect, state });

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, redirect);
  if (url.pathname !== "/callback") return res.writeHead(404).end();
  if (url.searchParams.get("state") !== state) return res.writeHead(400).end("State mismatch, try again.");
  const code = url.searchParams.get("code");
  if (!code) return res.writeHead(400).end(`Spotify said: ${url.searchParams.get("error") ?? "no code"}`);

  const tok = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      Authorization: "Basic " + Buffer.from(`${id}:${secret}`).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: redirect }),
  });
  const data = await tok.json();
  if (!tok.ok) {
    res.writeHead(500).end("Token exchange failed, see terminal.");
    console.error(data);
  } else {
    res.writeHead(200, { "Content-Type": "text/plain" }).end("Done. You can close this tab and go back to the terminal.");
    console.log("\nSPOTIFY_REFRESH_TOKEN=" + data.refresh_token + "\n");
  }
  server.close();
});

server.listen(8888, "127.0.0.1", () => {
  console.log("Open this link in your browser and approve access:\n\n" + authUrl + "\n");
});
