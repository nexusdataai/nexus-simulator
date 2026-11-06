#!/usr/bin/env node
/**
 * Parse data/Telco-Data/samples.js and emit JSON on stdout.
 * Usage: node scripts/export_telco_samples_fixtures.js > src/nexus_simulator/data/telco/sample_fixtures.json
 */
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const samplesPath = path.join(root, "data", "Telco-Data", "samples.js");
const code = fs.readFileSync(samplesPath, "utf8");

const window = {};
new Function("window", code)(window);
if (!window.SAMPLES) {
  console.error("No window.SAMPLES");
  process.exit(1);
}

const bssStart = code.indexOf("/* ============================ BSS");
const ossStart = code.indexOf("/* ============================ OSS");
const nssStart = code.indexOf("/* ============================ NSS");

function layerForKeyPos(pos) {
  if (nssStart >= 0 && pos >= nssStart) return "NSS";
  if (ossStart >= 0 && pos >= ossStart) return "OSS";
  return "BSS";
}

const out = {
  version: 1,
  source: "data/Telco-Data/samples.js",
  systems: {},
  counts: { BSS: 0, OSS: 0, NSS: 0 },
};

for (const systemKey of Object.keys(window.SAMPLES)) {
  const idx = code.indexOf(`"${systemKey}":`);
  const layer = layerForKeyPos(idx >= 0 ? idx : 0);
  out.counts[layer] += 1;
  const samp = window.SAMPLES[systemKey];
  const deliveries = {};
  for (const mode of ["Table", "File", "API", "Stream"]) {
    if (samp[mode] !== undefined) deliveries[mode] = samp[mode];
  }
  out.systems[systemKey] = { layer, deliveries };
}

process.stdout.write(JSON.stringify(out, null, 2));
