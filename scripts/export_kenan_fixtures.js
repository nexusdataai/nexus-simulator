#!/usr/bin/env node
/**
 * Parse data/Telco-Data/kenan.js and emit Kenan BP feed samples as JSON.
 * Usage: node scripts/export_kenan_fixtures.js > src/nexus_simulator/data/telco/kenan_feed_fixtures.json
 */
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const kenanPath = path.join(root, "data", "Telco-Data", "kenan.js");
const code = fs.readFileSync(kenanPath, "utf8");

const start = code.indexOf("Object.assign(window.SAMPLES");
const stop = code.indexOf("\n(function(){", start);
if (start < 0 || stop < 0) {
  console.error("Could not locate SAMPLES block in kenan.js");
  process.exit(1);
}
const window = { SAMPLES: {} };
new Function("window", code.slice(start, stop))(window);
if (!window.SAMPLES || !Object.keys(window.SAMPLES).length) {
  console.error("No window.SAMPLES in kenan.js");
  process.exit(1);
}

const out = {
  version: 1,
  source: "data/Telco-Data/kenan.js",
  feeds: {},
};

for (const [feedName, samp] of Object.entries(window.SAMPLES)) {
  const deliveries = {};
  for (const mode of ["Table", "File", "API", "Stream"]) {
    if (samp[mode] !== undefined) deliveries[mode] = samp[mode];
  }
  out.feeds[feedName] = { deliveries };
}

process.stdout.write(JSON.stringify(out, null, 2));