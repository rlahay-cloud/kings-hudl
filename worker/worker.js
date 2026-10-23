// Kings HUDL submit helper. Runs on Cloudflare Workers.
// Takes highlight or shot files from the site and saves them into the games folder of the GitHub repo.
// Settings it needs (set in the Cloudflare dashboard):
//   GITHUB_TOKEN   secret   a GitHub token that can only write to this one repo
//   PASSCODE       secret   the passcode you give the coaches
//   REPO           text     rlahay-cloud/kings-hudl
//   ALLOWED_ORIGIN text     https://rlahay-cloud.github.io

const CLIP_LINE = /^\d+:\d{2}:\d{2}\|[^|\n]{1,30}\|[\da ]{0,60}\|[^|\n]{0,200}(\|\d{1,7})?$/;
const SHOT_LINE = /^P\d+\|[\d.]+\|[\d.]+\|(-|\d+)\|(G|S)\|(H|A)$/;
const MAX_BYTES = 60000;

function cors(env, extra) {
  return Object.assign({
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  }, extra || {});
}
function reply(env, status, obj) {
  return new Response(JSON.stringify(obj), {status: status, headers: cors(env, {"Content-Type": "application/json"})});
}
function same(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
function slugify(name) {
  return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 20);
}
function b64(text) {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
// Checks a request body. Returns {path, text, coach} or {error}.
function check(body, env) {
  if (!body || typeof body !== "object") return {error: "Bad request"};
  if (!same(body.passcode, env.PASSCODE || "")) return {error: "Wrong passcode"};
  if (body.kind !== "clips" && body.kind !== "shots" && body.kind !== "video") return {error: "Unknown kind"};
  if (!/^\d{4}-\d{2}-\d{2}$/.test(body.date || "")) return {error: "Bad date"};
  if (body.kind === "video") {
    const u = String(body.text || "").trim();
    if (!/^https:\/\/(www\.|m\.)?(youtube\.com|youtu\.be)\/[^\s]{3,200}$/.test(u)) return {error: "That does not look like a YouTube link"};
    return {path: "games/video_" + body.date + ".txt", text: u + "\n", coach: "video"};
  }
  const coach = slugify(body.coach) || "team";
  const text = String(body.text || "");
  if (text.length > MAX_BYTES) return {error: "File is too big"};
  const lines = text.split(/\r?\n/).filter(function (l) { return l.trim() !== ""; });
  if (lines.length > 3000) return {error: "Too many lines"};
  const re = body.kind === "clips" ? CLIP_LINE : SHOT_LINE;
  for (const l of lines) if (!re.test(l)) return {error: "A line was not in the right format"};
  return {path: "games/" + body.kind + "_" + body.date + "_" + coach + ".txt", text: lines.join("\n") + "\n", coach: coach};
}

async function saveToGitHub(env, path, text, message) {
  const url = "https://api.github.com/repos/" + env.REPO + "/contents/" + path;
  const headers = {
    "Authorization": "Bearer " + env.GITHUB_TOKEN,
    "Accept": "application/vnd.github+json",
    "User-Agent": "kings-hudl-submit",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  let sha;
  const cur = await fetch(url + "?ref=main", {headers: headers});
  if (cur.status === 200) sha = (await cur.json()).sha;
  else if (cur.status !== 404) throw new Error("GitHub read " + cur.status);
  const put = await fetch(url, {
    method: "PUT", headers: Object.assign({"Content-Type": "application/json"}, headers),
    body: JSON.stringify({message: message, content: b64(text), branch: "main", sha: sha}),
  });
  if (!put.ok) throw new Error("GitHub write " + put.status);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, {status: 204, headers: cors(env)});
    if (request.method !== "POST") return reply(env, 405, {ok: false, error: "Use POST"});
    const origin = request.headers.get("Origin");
    if (origin && origin !== env.ALLOWED_ORIGIN) return reply(env, 403, {ok: false, error: "Not allowed from this site"});
    let body;
    try { body = await request.json(); } catch (e) { return reply(env, 400, {ok: false, error: "Bad request"}); }
    if (body && body.kind === "check") {
      if (!same(body.passcode, env.PASSCODE || "")) return reply(env, 401, {ok: false, error: "Wrong passcode"});
      return reply(env, 200, {ok: true});
    }
    const r = check(body, env);
    if (r.error) return reply(env, r.error === "Wrong passcode" ? 401 : 400, {ok: false, error: r.error});
    try {
      await saveToGitHub(env, r.path, r.text, (body.kind === "clips" ? "Highlights" : body.kind === "video" ? "Video link" : "Shots") + " from " + r.coach + " for " + body.date);
    } catch (e) {
      const why = String(e && e.message || e);
      let hint = "";
      if (/ 401$/.test(why)) hint = " (the GitHub key is wrong or expired)";
      else if (/ 403$/.test(why)) hint = " (the GitHub key does not have Contents read and write)";
      else if (/ 404$/.test(why)) hint = " (the GitHub key cannot see the repo, or REPO is spelled wrong)";
      else if (/ 422$/.test(why)) hint = " (GitHub refused the file)";
      else if (!/GitHub (read|write) \d+$/.test(why)) hint = " (GITHUB_TOKEN or REPO is missing in the helper settings)";
      return reply(env, 502, {ok: false, error: "Could not save to GitHub, " + why + hint});
    }
    return reply(env, 200, {ok: true, file: r.path});
  },
};
