// GET /api/token-status
// Tells the profile's daily workflow how many days the Spotify sign-in has left,
// so it can open a GitHub issue before the card stops working.
// Returns dates and a yes/no only; never a token.

import { tokenStatus } from "../lib/tokens.js";

export default async function handler(req, res) {
  let body;
  try {
    body = await tokenStatus();
  } catch (err) {
    console.error(err);
    body = { known: false, failing: false, error: "Could not read the token status." };
  }
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).send(JSON.stringify(body));
}
