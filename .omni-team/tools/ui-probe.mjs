#!/usr/bin/env node
// omni-team UI probe: opens a page in a real browser at several widths, runs the in-page
// measurements (ui-probe-page.js), saves a full-page screenshot per width, captures console
// errors and failed requests, and can sweep the width to find the ranges where layout breaks.
// It only reads the page. Used by the smoke-tester role (team/smoke-tester.md).
//
//   node ui-probe.mjs <url> [--widths 375,768,1280,1440] [--height 900] [--out <dir>]
//                    [--sweep [1440,375,20]] [--wait 600] [--min-target 24] [--dark] [--pw <dir>]
//   node ui-probe.mjs --check        # can a browser start? prints which one
//
// Needs Node 18+ and the `playwright` package, looked up in --pw, .omni-team/.venv/node (set up
// by `orchestrator.py setup --ui-probe`), the current directory, then this folder. It starts
// Playwright's Chromium, else an installed Chrome or Edge. Never install it into the project.
//
// Exit codes: 0 nothing found · 1 findings or errors · 2 usage · 3 browser library or browser missing · 4 page did not load

import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pageProbe = readFileSync(join(here, "ui-probe-page.js"), "utf8").trim();
const sweepChecks = ["horizontal_scroll", "clipped_text", "wrapped_label"];
const maxErrors = 20;
const installHint = [
  "Playwright and a browser are needed. Set them up inside .omni-team/.venv (git-ignored):",
  "  python3 .omni-team/orchestrator.py setup --ui-probe",
  "Or run ui-probe-page.js through your browser tool's evaluate at each width instead.",
].join("\n");

function usage(message) {
  console.error(`${message}\nusage: node ui-probe.mjs <url> [--widths 375,768,1280,1440] [--sweep [from,to,step]] [--out <dir>] [--pw <dir>]`);
  process.exit(2);
}

function numbers(value, flag) {
  const list = String(value ?? "").split(",").map(Number);
  if (!list.length || list.some((n) => !Number.isFinite(n) || n <= 0)) usage(`${flag}: expected positive numbers, got "${value}"`);
  return list;
}

function parseArgs(argv) {
  const options = { url: "", widths: [375, 768, 1280, 1440], height: 900, out: "", sweep: null,
    waitMs: 600, minTarget: 24, dark: false, pw: "", check: false };
  const rest = [...argv];
  while (rest.length) {
    const arg = rest.shift();
    if (arg === "--widths") options.widths = numbers(rest.shift(), arg);
    else if (arg === "--height") [options.height] = numbers(rest.shift(), arg);
    else if (arg === "--out") options.out = rest.shift();
    else if (arg === "--wait") options.waitMs = Number(rest.shift());
    else if (arg === "--min-target") [options.minTarget] = numbers(rest.shift(), arg);
    else if (arg === "--pw") options.pw = rest.shift();
    else if (arg === "--dark") options.dark = true;
    else if (arg === "--check") options.check = true;
    else if (arg === "--sweep") {
      const [from, to, step = 20] = /^\d+,\d+(,\d+)?$/.test(rest[0] ?? "") ? numbers(rest.shift(), arg) : [1440, 375];
      options.sweep = { from: Math.max(from, to), to: Math.min(from, to), step };
    } else if (arg.startsWith("--")) usage(`unknown option ${arg}`);
    else options.url = arg;
  }
  if (!options.check && !/^(https?|file):/.test(options.url)) usage(`a http(s) or file URL is required, got "${options.url}"`);
  options.out = resolve(options.out || join(tmpdir(), `omni-probe-${Date.now()}`));
  return options;
}

function loadPlaywright(dirs) {
  for (const dir of dirs.filter(Boolean)) {
    try {
      return createRequire(join(resolve(dir), "noop.js"))("playwright");
    } catch {
      // not in this folder; try the next one
    }
  }
  return null;
}

// Playwright's own Chromium first; an installed Chrome or Edge spares the browser download.
async function launch(playwright) {
  const failures = [];
  for (const channel of [undefined, "chrome", "msedge"]) {
    try {
      const browser = await playwright.chromium.launch(channel ? { channel } : {});
      browser.omniChannel = channel || "chromium";
      return browser;
    } catch (err) {
      failures.push(`${channel || "chromium"}: ${String(err.message).split("\n")[0]}`);
    }
  }
  console.error(`No browser started:\n  ${failures.join("\n  ")}\n${installHint}`);
  process.exit(3);
}

function watchErrors(page) {
  const errors = new Set();
  const note = (line) => errors.size < maxErrors && errors.add(line.slice(0, 300));
  page.on("console", (msg) => msg.type() === "error" && note(`console: ${msg.text()}`));
  page.on("pageerror", (err) => note(`page error: ${err.message}`));
  page.on("requestfailed", (req) => note(`request failed: ${req.method()} ${req.url()} (${req.failure()?.errorText})`));
  page.on("response", (res) => res.status() >= 400 && note(`HTTP ${res.status()}: ${res.url()}`));
  return errors;
}

const measure = (page, opts) => page.evaluate(`(${pageProbe})(${JSON.stringify(opts)})`);

async function probeWidths(page, options) {
  const results = [];
  for (const width of options.widths) {
    await page.setViewportSize({ width, height: options.height });
    const response = await page.goto(options.url, { waitUntil: "load", timeout: 30000 });
    if (!response || response.status() >= 400) throw new Error(`HTTP ${response ? response.status() : "no response"}`);
    await page.waitForTimeout(options.waitMs);
    const screenshot = join(options.out, `${width}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    results.push({ ...(await measure(page, { minTarget: options.minTarget })), screenshot });
  }
  return results;
}

// Resizes without reloading, as a person dragging the window would, and reports the width
// ranges in which each check fires.
async function sweep(page, options) {
  const { from, to, step } = options.sweep;
  await page.setViewportSize({ width: from, height: options.height });
  await page.goto(options.url, { waitUntil: "load", timeout: 30000 });
  await page.waitForTimeout(options.waitMs);
  const ranges = {};
  const widths = [];
  for (let width = from; width > to; width -= step) widths.push(width);
  let previous = null;
  for (const width of [...widths, to]) {
    await page.setViewportSize({ width, height: options.height });
    await page.waitForTimeout(120);
    const result = await measure(page, { only: sweepChecks, maxPerCheck: 1 });
    for (const check of Object.keys(result.counts)) {
      const list = (ranges[check] = ranges[check] || []);
      const last = list[list.length - 1];
      if (last && last.to === previous) last.to = width;
      else list.push({ from: width, to: width, example: result.issues[check][0] });
    }
    previous = width;
  }
  return ranges;
}

function detail(issue) {
  const extra = Object.entries(issue).filter(([key]) => key !== "at" && key !== "text")
    .map(([key, value]) => `${key} ${value}`).join(", ");
  return `\`${issue.at}\`${issue.text ? ` "${issue.text}"` : ""}${extra ? ` — ${extra}` : ""}`;
}

function report(options, results, ranges, errors) {
  const lines = [`# UI probe — ${options.url}`, "", `Screenshots and probe.json: ${options.out}`, "",
    "| Width | Page width | Findings |", "|---|---|---|"];
  for (const r of results) {
    const found = Object.entries(r.counts).map(([check, n]) => `${check} ${n}`).join(", ") || "none";
    lines.push(`| ${r.viewport.width} | ${r.scroll_width} | ${found} |`);
  }
  for (const r of results.filter((x) => Object.keys(x.counts).length)) {
    lines.push("", `## ${r.viewport.width}px`);
    for (const [check, list] of Object.entries(r.issues)) {
      lines.push(`- **${check}** ×${r.counts[check]}`, ...list.map((issue) => `  - ${detail(issue)}`));
    }
  }
  if (ranges) {
    const { from, to, step } = options.sweep;
    lines.push("", `## Width sweep ${from}→${to}px, step ${step}`);
    const found = Object.entries(ranges);
    if (!found.length) lines.push("- nothing fired");
    for (const [check, list] of found) {
      for (const range of list) lines.push(`- **${check}** at ${range.from}–${range.to}px: ${detail(range.example)}`);
    }
  }
  lines.push("", "## Errors captured", ...(errors.size ? [...errors].map((e) => `- ${e}`) : ["- none"]));
  return lines.join("\n");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const playwright = loadPlaywright([options.pw, join(here, "..", ".venv", "node"), process.cwd(), here]);
  if (!playwright) {
    console.error(installHint);
    process.exit(3);
  }
  const browser = await launch(playwright);
  if (options.check) {
    console.log(`browser ready: ${browser.omniChannel} ${browser.version()}`);
    await browser.close();
    process.exit(0);
  }
  mkdirSync(options.out, { recursive: true });
  const context = await browser.newContext({ colorScheme: options.dark ? "dark" : "light" });
  const page = await context.newPage();
  const errors = watchErrors(page);
  let results;
  let ranges = null;
  try {
    results = await probeWidths(page, options);
    if (options.sweep) ranges = await sweep(page, options);
  } catch (err) {
    console.error(`Page did not load: ${options.url} — ${String(err.message).split("\n")[0]}`);
    await browser.close();
    process.exit(4);
  }
  await browser.close();
  writeFileSync(join(options.out, "probe.json"), JSON.stringify({ url: options.url, results, sweep: ranges, errors: [...errors] }, null, 2));
  console.log(report(options, results, ranges, errors));
  const findings = results.some((r) => Object.keys(r.counts).length) || (ranges && Object.keys(ranges).length) || errors.size;
  process.exit(findings ? 1 : 0);
}

main();
