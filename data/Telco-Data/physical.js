// "Physical layer" tab: the six network layers as an infographic, a physical topology drawing
// (devices → cell site → transport → metro → core → data centres → internet) and a detail card per site.
// Renders through physicalHTML(); uses the page's esc(), state, render() and setView().

const PHYS_ROWS = [
 { id:"ran",   title:"Access / RAN",      sub:"Last mile",             tone:"neutral",   chips:["Cell sites","FTTH / OLT","Enterprise CPE"] },
 { id:"atx",   title:"Access transport",  sub:"Cell site to hub",      tone:"transport", chips:["Cell site router","Pre-aggregation","Fibre / microwave"] },
 { id:"metro", title:"Metro aggregation", sub:"City / region",         tone:"transport", chips:["AGG routers","Metro rings","BNG / edge"] },
 { id:"tcore", title:"Transport core",    sub:"IP / MPLS backbone",    tone:"transport", chips:["P routers","PE routers","SR / RSVP-TE"] },
 { id:"dc",    title:"Packet core",       sub:"Hosted in DCs",         tone:"pcore",     chips:["UPF (edge DC)","AMF, SMF, UDM","IMS, PCF"] },
 { id:"inet",  title:"Internet / peering",sub:"Outside the operator",  tone:"neutral",   chips:["Transit / IXP","Cloud on-ramps","Other operators"] }
];

const SITES = {
 dev: { title:"Devices & premises", sub:"Where the customer is", toLayer:"pcore",
   what:"The customer's own equipment. A phone is known to the network by its SIM (the IMSI) and by the handset itself (the IMEI); a home by its fibre terminal (ONT); a business by its router (CPE).",
   inside:[["Phone or modem","The SIM or eSIM holds the IMSI; the handset has an IMEI"],["Home fibre terminal (ONT)","On the wall at home; connects over a passive optical network to an OLT"],["Enterprise CPE","Business router on a dedicated fibre or 5G fixed-wireless link"]],
   scale:"Millions of devices; one customer can have several lines and devices.",
   fails:["Older or non-5G handsets limit speed","Poor indoor coverage","Device or SIM swaps can signal churn or fraud"],
   data:[["Device and IMEI changes (EIR)","Table"],["Per-session experience from probes","Stream"]] },
 ran: { title:"RAN site", sub:"Cell site: tower or rooftop", toLayer:"ran",
   what:"A mast or rooftop that serves the surrounding area by radio. A site is usually split into three sectors of about 120° each, and each sector carries several frequency bands. One band in one sector is one cell, so site RYD-0421 carries cells such as RYD-0421-L18-1 (LTE 1800, sector 1).",
   inside:[["Antennas / AAU","Panels at the top, one per sector; 5G uses active antenna units"],["Remote radio units","Mounted beside the antennas; amplify and convert the radio signal"],["Baseband unit (BBU / DU)","In the cabinet at the base; processes the signal for every cell on the site"],["Cell site router","Connects the site to the transport network"],["Power","Rectifiers and batteries, plus a generator or solar on remote sites"],["Fibre or microwave dish","The backhaul link toward the hub"],["Exchange with OLT (fixed)","Serves homes over fibre (PON); sits in the same access layer"]],
   scale:"Thousands to tens of thousands of sites per operator, each with several cells.",
   fails:["Mains power cut, then batteries run out","Antenna or feeder faults (VSWR alarms)","Overheating cabinets","Backhaul lost: the whole site goes off air"],
   data:[["Alarms","Stream"],["PM counters per cell, every 15 min","File"],["Cell configuration (tilt, PCI)","File"]] },
 atx: { title:"Access transport", sub:"Cell site to hub", toLayer:"atx",
   what:"Backhaul links that carry each cell site's traffic to a hub site. Sites are often chained, so one hub collects five to twenty sites; when the hub link fails, every site behind it goes down at once.",
   inside:[["Fibre","Highest capacity; buried or on poles, at risk from digging"],["Microwave","Point-to-point radio between dishes; quick to deploy, affected by heavy rain and dust"],["Hub site","Pre-aggregation router collecting traffic from several cell sites"],["Cell site router","At every site; the first IP hop"]],
   scale:"One hub for every 5–20 cell sites.",
   fails:["Fibre cuts from road and building works","Microwave fading or misaligned dishes","A hub failure takes down every site behind it"],
   data:[["Link alarms","Stream"],["Interface telemetry","Stream"],["Utilisation, every 15 min","File"]] },
 metro: { title:"Metro aggregation", sub:"City / region POPs", toLayer:"metro",
   what:"Aggregation routers in points of presence (POPs) across a city, joined in rings so that one fibre cut does not isolate an area. Broadband network gateways (BNG) for fixed customers sit here too.",
   inside:[["AGG routers","Collect traffic from many hub sites"],["Metro rings","Traffic can travel either way round the ring"],["BNG / edge","Authenticates fixed broadband sessions and assigns IP addresses"],["POP building","Racks, power, cooling and fibre patching"]],
   scale:"Tens of POPs in a large city.",
   fails:["Two cuts on the same ring isolate the area between them","Congested aggregation links at busy hour"],
   data:[["Alarms and syslog","Stream"],["Telemetry","Stream"],["Fixed broadband sessions","File"]] },
 tcore: { title:"Transport core", sub:"National IP / MPLS backbone", toLayer:"tcore",
   what:"Long-haul fibre and high-capacity routers that connect cities, data centres and internet exchanges. P routers in the middle forward traffic; PE routers sit at the edge of the backbone, where metro networks, data centres and peering connect.",
   inside:[["P routers","Forward labelled traffic across the backbone"],["PE routers","Edge of the backbone: where metro, DCs and peering attach"],["Long-haul fibre and DWDM","Many wavelengths on one fibre pair over hundreds of kilometres"],["SR / RSVP-TE","Steers traffic onto chosen paths and reroutes around failures"]],
   scale:"A handful of core POPs, fully meshed.",
   fails:["Rare but wide: one event can affect several regions","Long-haul fibre cuts (rerouted in milliseconds when protected)"],
   data:[["Telemetry","Stream"],["Flow records","File"],["Routing state","API"]] },
 dc: { title:"Data centres", sub:"Edge, core and IT", toLayer:"pcore",
   what:"The packet core and the IT systems run as software in data centres, usually on cloud-native platforms in geo-redundant pairs. This is where the NSS, BSS and OSS physically live.",
   inside:[["Edge DC","User plane (UPF) close to users for low latency, plus edge computing (MEC)"],["Core DC","Control plane: AMF and SMF (mobility and sessions), UDM (subscribers), IMS (voice), PCF (policy), plus MSC, EIR and NWDAF"],["IT DC or cloud","BSS (CRM, charging, billing), OSS (element managers, assurance, inventory), and the data and AI platform"],["DMZ","The staging server sits between the operator network and the AI platform"]],
   scale:"Two to four core DCs, more edge DCs; IT is often partly in public cloud.",
   fails:["Software faults or failed upgrades in network functions","Signalling storms when many phones reconnect after an outage","UPF capacity limits at busy hour"],
   data:[["CDRs","File"],["Mobility events","Stream"],["Policy events","Stream"],["Subscriber profiles","API"]] },
 inet: { title:"Internet & peering", sub:"Outside the operator", toLayer:"inet",
   what:"Where the operator's network meets everyone else: internet transit providers, exchange points, private links to cloud and content providers, and roaming partners over the IPX network.",
   inside:[["Transit / IXP","Paid transit and shared exchange points"],["Cloud on-ramps","Private links to large cloud and content providers"],["IPX / roaming","Other operators' networks for roaming, with signalling through DRA / SEPP"]],
   scale:"A few peering locations, usually in the largest cities.",
   fails:["Congested peering slows down popular apps","Roaming registration failures abroad"],
   data:[["TAP3 roaming files","File"],["Roaming signalling","Stream"],["Peering flows","File"]] }
};

const ZONES = [["dev",0,120,"Devices"],["ran",120,320,"RAN site"],["atx",320,460,"Access transport"],["metro",460,650,"Metro aggregation"],["tcore",650,830,"Transport core"],["dc",830,1080,"Data centres"],["inet",1080,1200,"Internet"]];

function physSVG(){
  const sel = state.site;
  const t = (x, y, s, cls = "ph-t", anchor = "middle") => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${esc(s)}</text>`;
  const router = (x, y) => `<circle cx="${x}" cy="${y}" r="11" class="ph-node"/><path d="M${x-6} ${y}h12M${x} ${y-6}v12" class="ph-nodex"/>`;
  const rack = (x, y) => `<rect x="${x}" y="${y}" width="14" height="34" rx="2" class="ph-rack"/><path d="M${x+3} ${y+8}h8M${x+3} ${y+15}h8M${x+3} ${y+22}h8" class="ph-rackl"/>`;
  const cloud = (cx, cy) => `<path d="M${cx-42} ${cy+14} a18 18 0 0 1 4-34 a24 24 0 0 1 44-6 a18 18 0 0 1 32 16 a14 14 0 0 1-6 24 z" class="ph-cloud"/>`;
  let s = `<svg viewBox="0 0 1200 455" role="img" aria-label="Physical network from devices to the internet">`;
  // zones (click targets sit behind the artwork; artwork ignores the pointer)
  ZONES.forEach(([id, x0, x1, label], i) => {
    s += `<rect x="${x0 + 2}" y="34" width="${x1 - x0 - 4}" height="370" rx="8" class="ph-zone${i % 2 ? " alt" : ""}${sel === id ? " sel" : ""}" data-site="${id}" role="button" tabindex="0" aria-label="${esc(SITES[id].title)}"/>`;
    s += t((x0 + x1) / 2, 22, label.toUpperCase(), "ph-h" + (sel === id ? " on" : ""));
  });
  s += `<g class="ph-art">`;
  // links (drawn first, under the icons)
  s += `<path d="M240 268 L360 220" class="ph-fibre"/>${t(296, 236, "Fibre", "ph-s ph-acc")}`;
  s += `<path d="M254 129 L388 184" class="ph-mw"/>${t(300, 133, "Microwave", "ph-s ph-acc")}`;
  s += `<path d="M330 150 L362 196 M330 300 L362 230" class="ph-faint"/>${t(338, 318, "more sites", "ph-s")}`;
  s += `<path d="M72 232 L190 340 M72 336 L190 350" class="ph-fibre"/>`;
  s += `<path d="M250 352 C 380 380, 500 340, 548 288" class="ph-fibre"/>`;
  s += `<path d="M420 212 L482 215" class="ph-fibre"/>`;
  s += `<circle cx="555" cy="215" r="62" class="ph-ring"/>`;
  s += `<path d="M628 210 L689 164 M628 220 L689 266" class="ph-fibre"/>`;
  s += `<path d="M700 160 L785 160 L785 270 L700 270 Z M700 160 L785 270 M785 160 L700 270" class="ph-mesh"/>`;
  s += `<path d="M796 156 L850 112 M796 164 L850 214 M796 266 L850 236 M796 274 L850 336" class="ph-fibre"/>`;
  s += `<path d="M1060 108 L1098 160 M1060 220 L1098 172 M1060 236 L1100 292 M1060 340 L1100 304" class="ph-fibre"/>`;
  // management network
  s += `<path d="M242 276 H266 V420 M420 230 H434 V420 M610 244 V420 M742 322 V420 M955 392 V420 M266 420 H955" class="ph-mgmt"/>`;
  s += t(588, 442, "Management network (DCN): alarms, PM files and configuration flow from every site to the OSS in the IT data centre", "ph-s ph-ossc");
  // devices
  s += `<rect x="47" y="96" width="26" height="46" rx="5" class="ph-icon"/><path d="M55 136h10" class="ph-iconl"/>`;
  s += t(60, 160, "Phone") + t(60, 174, "SIM · eSIM", "ph-s");
  s += `<path d="M42 236 L60 220 L78 236 V256 H42 Z" class="ph-icon"/><rect x="55" y="244" width="10" height="12" class="ph-iconl"/>`;
  s += t(60, 274, "Home · ONT");
  s += `<rect x="44" y="318" width="32" height="38" rx="2" class="ph-icon"/><path d="M50 326h6M64 326h6M50 336h6M64 336h6M50 346h6M64 346h6" class="ph-iconl"/>`;
  s += t(60, 374, "Enterprise CPE");
  // radio waves
  s += `<path d="M194 76 q-9 12 0 24 M184 70 q-14 18 0 36 M174 64 q-19 24 0 48" class="ph-radio"/>`;
  s += `<path d="M150 100 L80 112" class="ph-radiol"/>${t(118, 98, "Radio", "ph-s")}`;
  // tower
  s += `<path d="M202 262 L216 78 L224 78 L238 262 M205 222 L235 222 M208 182 L232 182 M211 142 L229 142 M213 110 L227 110 M205 222 L232 182 L208 182 L229 142 L211 142 L227 110" class="ph-tower"/>`;
  s += `<rect x="206" y="58" width="7" height="24" rx="1" class="ph-ant"/><rect x="216.5" y="54" width="7" height="26" rx="1" class="ph-ant"/><rect x="227" y="58" width="7" height="24" rx="1" class="ph-ant"/>`;
  s += `<rect x="206" y="88" width="7" height="9" class="ph-rru"/><rect x="227" y="88" width="7" height="9" class="ph-rru"/>`;
  s += `<path d="M244 120 a10 10 0 0 1 0 18 z" class="ph-dish"/><path d="M228 129 H244" class="ph-iconl"/>`;
  s += `<rect x="198" y="262" width="44" height="24" rx="3" class="ph-cab"/>${t(220, 278, "BBU", "ph-s ph-inv")}`;
  s += t(220, 304, "Cabinet: BBU,") + t(220, 318, "router, power", "ph-s");
  s += `<rect x="190" y="334" width="60" height="30" rx="3" class="ph-icon"/>${t(220, 353, "OLT", "ph-s")}`;
  s += t(220, 382, "Exchange (fixed)", "ph-s");
  // hub
  s += `<rect x="360" y="190" width="60" height="46" rx="4" class="ph-icon"/>${router(390, 213)}`;
  s += `<path d="M386 190 a8 8 0 0 1 14 0 z" class="ph-dish"/>`;
  s += t(390, 256, "Hub site") + t(390, 270, "pre-aggregation", "ph-s");
  // metro
  s += router(493, 215) + router(555, 153) + router(617, 215) + router(555, 277);
  s += t(555, 132, "AGG routers") + t(555, 104, "Metro ring", "ph-s") + t(555, 302, "BNG / edge", "ph-s");
  // core mesh
  s += router(700, 160) + router(785, 160) + router(700, 270) + router(785, 270);
  s += t(742, 132, "P / PE routers") + t(742, 300, "IP / MPLS backbone", "ph-s") + t(742, 314, "SR / RSVP-TE", "ph-s");
  // data centres
  const dc = (y, h, name, l1, l2) => `<rect x="850" y="${y}" width="210" height="${h}" rx="6" class="ph-dc"/>` + t(862, y + 22, name, "ph-t", "start") + t(862, y + 39, l1, "ph-s", "start") + (l2 ? t(862, y + 54, l2, "ph-s", "start") : "") + rack(992, y + h / 2 - 17) + rack(1010, y + h / 2 - 17) + rack(1028, y + h / 2 - 17);
  s += dc(70, 78, "Edge DC", "UPF · MEC");
  s += dc(178, 92, "Core DC", "AMF · SMF · UDM", "IMS · PCF · MSC · EIR");
  s += dc(300, 92, "IT DC / cloud", "BSS · OSS", "Data & AI platform");
  // internet
  s += cloud(1140, 172) + t(1140, 166, "Internet", "ph-t") + t(1140, 182, "Transit · IXP", "ph-s");
  s += cloud(1140, 304) + t(1140, 298, "Cloud · IPX", "ph-t") + t(1140, 314, "Roaming partners", "ph-s");
  s += `</g></svg>`;
  return s;
}

function physDetail(){
  const d = SITES[state.site]; if (!d) return "";
  return `<div class="pdetail" id="pdetail">
    <div class="ldh"><div><div class="eyebrow">Selected</div><h3>${esc(d.title)} <span class="lsub">${esc(d.sub)}</span></h3></div>
      <button type="button" class="act" data-to-layer="${d.toLayer}">See its data in the Data layer →</button></div>
    <p class="ldesc">${esc(d.what)}</p>
    <div class="pgrid">
      <div><h4>What is physically there</h4><dl class="pinside">${d.inside.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></div>
      <div><h4>Typical scale</h4><p class="small">${esc(d.scale)}</p>
        <h4>What usually goes wrong</h4><ul class="lai">${d.fails.map(f => `<li>${esc(f)}</li>`).join("")}</ul>
        <h4>Data it sends</h4><div class="pdata">${d.data.map(([l, m]) => `<span class="ditem"><span class="dc ${m}">${m}</span>${esc(l)}</span>`).join("")}</div></div>
    </div></div>`;
}

function physicalHTML(){
  if (!state.site) state.site = "ran";
  const rows = PHYS_ROWS.map(r => `<div class="prow t-${r.tone}${state.site === r.id ? " sel" : ""}" data-site="${r.id}" role="button" tabindex="0" aria-pressed="${state.site === r.id}">
      <div class="lt"><b>${r.title}</b><span>${r.sub}</span></div>
      <div class="pchips">${r.chips.map(c => `<span class="pchip">${esc(c)}</span>`).join("")}</div></div>`).join(`<div class="parrow" aria-hidden="true">↓</div>`);
  return `<section id="physical">
    <div class="shead"><h2>Physical layer</h2></div>
    <p class="sub">What the network physically is, from the phone to the internet. Select a layer or an area of the drawing to see what is installed there, what fails, and the data it sends.</p>
    <h3 class="parth">What it looks like on the ground</h3>
    <div class="pdiag">${physSVG()}</div>
    <div class="rlegend plegend">
      <span><span class="ln" style="border-top-color:var(--accent)"></span>Fibre</span>
      <span><span class="ln dash" style="border-top-color:var(--accent)"></span>Microwave</span>
      <span><span class="ln" style="border-top-color:var(--muted)"></span>Radio</span>
      <span><span class="ln dash" style="border-top-color:var(--oss)"></span>Management network to OSS</span>
      <span>Traffic flows left to right from the device to the internet.</span></div>
    <div class="psplit">
      <div><h3 class="parth">The six network layers</h3><div class="pstack">${rows}</div></div>
      <div><h3 class="parth">&nbsp;</h3>${physDetail()}</div>
    </div>
  </section>`;
}

function selectSite(id){
  state.site = id; render();
  const f = document.querySelector(`.prow[data-site="${id}"]`) ;
  const d = document.getElementById("pdetail");
  if (d) { const r = d.getBoundingClientRect(); if (r.top < 120 || r.top > innerHeight - 80) d.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
}

document.getElementById("main").addEventListener("click", e => {
  const tl = e.target.closest("[data-to-layer]");
  if (tl) { state.layer = tl.dataset.toLayer; setView("layers"); try { history.replaceState(null, "", "#layers"); } catch (err) {} return; }
  const s = e.target.closest("[data-site]"); if (s) selectSite(s.dataset.site);
});
document.getElementById("main").addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest("[data-site][role=button]")) {
    e.preventDefault(); const id = e.target.closest("[data-site]").dataset.site; selectSite(id);
    const again = document.querySelector(`[data-site="${id}"][role=button]`); if (again) again.focus({ preventScroll: true });
  }
});
