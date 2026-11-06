// "Telco layers" tab: network topology, where BSS / OSS / NSS sit, and how the AI stack processes the data.
// Renders into the main page through layersHTML(); uses the page's esc(), state, render(), openEntity() and domOf().

const LAYERS = [
 { id:"bss", band:true, title:"BSS", sub:"Commercial layer", tone:"bss",
   chips:["CRM","Catalog","Order","Charging (OCS / CHF)","Billing","Payments","Care","Campaign"],
   vendorLine:"Huawei BES / CBS · Ericsson · Amdocs · Salesforce · Oracle",
   desc:"Everything about the customer as a buyer: who they are, what they bought, what they used and paid, and every contact with care or digital channels. BSS touches the network in three places: charging (CHF / OCS talks to the packet core in real time), usage (CDRs arrive through mediation) and orders (product orders become service orders and network activation).",
   vendors:{ Huawei:"BES (CRM, catalog, order), CBS (charging and billing)", Ericsson:"Order Care, Ericsson Charging, Ericsson Billing (BSCS iX)", Amdocs:"CRM, Catalog, Charging, Billing, Data Hub", Salesforce:"Communications Cloud, Service Cloud, Marketing Cloud, Data Cloud", Oracle:"Siebel CRM, BRM, Elastic Charging Engine" },
   oss:["Not managed by OSS: BSS has its own application monitoring"],
   dataT:[["Customer, account, subscriptions","Oracle DB tables, Salesforce objects","Table"],["Customer, product, order, ticket records","TMF Open APIs, Salesforce REST","API"],["Rated EDRs, bill runs","CSV / ASN.1 EDR files, bill XML","File"],["Order, balance, digital events","Kafka JSON","Stream"]],
   tmf:["Customer","Product","ProductOrder","BillingAccount","CustomerBill","Bucket (prepay balance)","TroubleTicket (customer)","PartyInteraction"],
   ai:["Customer golden table: profile, plan, spend, contract end, recharges, payments","Churn and upsell signals: complaints, port-out, cancel-page visits, offer history","Actions land here: retention offers (TMF680), care notes, campaigns"],
   tab:"bss" },

 { id:"ran", title:"Access / RAN", sub:"Last mile", tone:"neutral",
   chips:["Cell sites (eNodeB / gNodeB)","FTTH / OLT","Enterprise CPE"],
   oss:["iMaster MAE","MantaRay NM","Ericsson ENM"], ossNote:"Radio FM · PM · CM · SON",
   data:[["Alarms","Stream"],["PM counters, 15 min","File"],["Bulk CM export","File"],["Cell inventory","Table"]],
   desc:"Radio and fixed access, where the customer's phone or premises connects. Coverage, congestion and outages that customers actually feel mostly start here, which makes this layer the first place to look when a subscriber's usage drops.",
   vendors:{ Huawei:"BTS / DBS radios, iMaster MAE", Nokia:"AirScale radios, MantaRay NM", Ericsson:"Ericsson Radio System, Ericsson Network Manager (ENM)", Others:"FTTH OLTs (Huawei, Nokia), enterprise CPE from many vendors" },
   dataT:[["Cell alarms (Cell Unavailable, VSWR …)","3GPP alarm fields over SNMP / CORBA / Kafka","Stream"],["PM counters per cell per 15 min","3GPP XML (TS 32.435), gzip","File"],["Cell parameters: tilt, PCI, TAC","Bulk CM XML, RAML","File"],["Sites, cells, coordinates, azimuth","Planning / inventory tables","Table"]],
   tmf:["Alarm","Resource (cell / site)","MeasurementCollectionJob","GeographicSite"],
   ai:["Detect outages and degraded KPIs against each cell's own baseline","Explain a subscriber's usage drop by their home cell's availability and congestion","Flag config changes (tilt) that cause lasting coverage loss"],
   tab:"oss" },

 { id:"atx", title:"Access transport", sub:"Cell site to hub", tone:"transport",
   chips:["Cell site router","Pre-aggregation","Fibre / microwave"],
   oss:["iMaster NCE","Nokia NSP","ENM (MINI-LINK)"], ossNote:"Transport FM · PM · topology",
   data:[["Link alarms","Stream"],["Interface telemetry","Stream"],["Utilisation, 15 min","File"],["Topology","API"]],
   desc:"Backhaul that carries traffic from each cell site to the first hub, over fibre or microwave. When a backhaul link fails, every cell behind it goes down, so this layer often holds the root cause of what looks like a radio outage.",
   vendors:{ Huawei:"ATN routers, RTN microwave, iMaster NCE", Nokia:"7250 IXR, Wavence microwave, Network Services Platform (NSP)", Ericsson:"Router 6000, MINI-LINK, ENM", Others:"Ciena, Cisco" },
   dataT:[["Link down / RDI alarms","SNMP traps, Kafka","Stream"],["Interface counters","gRPC telemetry","Stream"],["Utilisation, errored seconds","CSV PM export","File"],["Links and nodes","NETCONF / RESTCONF","API"]],
   tmf:["Alarm","Resource (cell / site)","ServiceProblem"],
   ai:["Root-cause ranking: a backhaul link failure explains the cell alarms behind it","Capacity forecasting for congested backhaul","Impact sizing: subscribers homed on every cell behind a link"],
   tab:"oss" },

 { id:"metro", title:"Metro aggregation", sub:"City / region", tone:"transport",
   chips:["AGG routers","Metro rings","BNG / edge"],
   oss:["iMaster NCE","Nokia NSP","Cisco Crosswork"], ossNote:"IP FM · PM · services",
   data:[["Alarms, syslog","Stream"],["Telemetry","Stream"],["BNG sessions (fixed)","File"]],
   desc:"Aggregation routers and metro rings that collect traffic from many hubs across a city or region. Broadband network gateways (BNG) for fixed customers also sit here.",
   vendors:{ Huawei:"NetEngine routers, iMaster NCE", Nokia:"7750 SR, NSP", Ericsson:"Router 6000", Others:"Cisco ASR / NCS, Juniper MX" },
   dataT:[["Router and ring alarms, syslog","SNMP, syslog, Kafka","Stream"],["Interface and queue telemetry","gRPC / SNMP","Stream"],["Fixed broadband sessions","RADIUS accounting files","File"]],
   tmf:["Alarm","Resource (cell / site)","ServiceProblem"],
   ai:["Congestion prediction on rings and aggregation links","Ring failure impact across many sites","Fixed broadband experience for convergent customers"],
   tab:"oss" },

 { id:"tcore", title:"Transport core", sub:"IP / MPLS backbone", tone:"transport",
   chips:["P routers","PE routers","SR / RSVP-TE"],
   oss:["iMaster NCE","Nokia NSP","Cisco Crosswork"], ossNote:"Backbone FM · PM · TE",
   data:[["Telemetry","Stream"],["Flow records","File"],["Routing state","API"]],
   desc:"The national IP / MPLS backbone that connects regions, data centres and peering points. Problems here are rare but wide, affecting many regions at once.",
   vendors:{ Huawei:"NetEngine 8000 / 9000, iMaster NCE", Nokia:"7750 SR / 7950 XRS, NSP", Ericsson:"Router 6000 (edge)", Others:"Cisco, Juniper" },
   dataT:[["Interface and LSP telemetry","gRPC telemetry","Stream"],["Traffic flows","NetFlow / IPFIX files","File"],["Routing and TE state","NETCONF / RESTCONF","API"]],
   tmf:["Resource (cell / site)","Alarm","ServiceProblem"],
   ai:["Traffic engineering and capacity planning","Backbone anomaly detection","Separating a regional backbone event from local radio issues"],
   tab:"oss" },

 { id:"pcore", title:"Packet core", sub:"Hosted in DCs", tone:"nss", nss:true,
   chips:["UPF (edge DC)","AMF · SMF · UDM","IMS · PCF","MSC · EIR · NWDAF"],
   oss:["iMaster MAE (core)","MantaRay NM","Ericsson ENM"], ossNote:"Core FM · PM, plus vendor core EMS",
   data:[["CDRs (ASN.1)","File"],["Mobility events","Stream"],["Policy events","Stream"],["Subscriber profiles","API"]],
   desc:"The NSS: the core network functions that register devices, set up sessions and calls, apply policy and generate usage records. This is where network data first gets a subscriber identity (IMSI / MSISDN), which makes it the bridge between OSS facts about cells and BSS facts about customers.",
   vendors:{ Huawei:"UNC, UDG, UDM, UPCF, CloudCore IMS", Nokia:"Cloud Packet Core, Cloud Mobility Manager, Cloud SDM, Cloud Session Core", Ericsson:"PCC / PCG, UDM / HSS, SAPC, vCSCF / MTAS", Oracle:"Cloud Native Core (PCF, UDR, SCP, SEPP, NWDAF)" },
   dataT:[["Voice, data and IMS CDRs","ASN.1 BER files (3GPP TS 32.298)","File"],["Attach / registration events","Ericsson EBM, Huawei CHR","Stream"],["Throttling, QoS changes","Diameter Gx / N7, Kafka","Stream"],["Subscriber network profile","LDAP / REST provisioning","API"],["Real-time charging","Nchf to CHF","Stream"]],
   tmf:["Usage","Service","LogicalResource (IMSI / MSISDN / SIM)","Event (network)","PhysicalResource (device)"],
   ai:["Per-subscriber usage trend (current vs prior window)","Attach and VoLTE failures as experience signals","Separate fair-usage throttling from network faults","Home cell per subscriber: the key that joins OSS data to customers"],
   tab:"nss" },

 { id:"inet", title:"Internet / peering", sub:"Outside the operator", tone:"neutral",
   chips:["Transit / IXP","Cloud on-ramps","Other operators"],
   oss:["Peering and roaming tools","Signalling (DRA / SEPP)"], ossNote:"Mostly partner-facing",
   data:[["TAP3 roaming files","File"],["Roaming signalling","Stream"],["Peering flow stats","File"]],
   desc:"Everything beyond the operator's own network: internet transit and exchange points, cloud providers, and other operators for roaming and interconnect.",
   vendors:{ Others:"Clearing houses (Syniverse, BICS), IXPs, cloud providers", Oracle:"Diameter Signaling Router, Cloud Native Core SEPP", Nokia:"Cloud Signaling Director", Ericsson:"Signaling Controller" },
   dataT:[["Roaming usage","TAP3 ASN.1 files via clearing house","File"],["Roaming signalling (S6a, N32)","DRA / SEPP xDR, Kafka","Stream"],["Peering traffic","NetFlow / IPFIX","File"]],
   tmf:["Usage","Event (network)"],
   ai:["Roaming bill shock and travel patterns (upsell)","Roaming registration failures","Peering cost and route optimisation"],
   tab:"nss" },

 { id:"oss", band:true, title:"OSS", sub:"Cross-layer operations", tone:"oss",
   chips:["Service assurance & correlation","Probes / CEM","Inventory","Orchestration & activation","Tickets & change"],
   vendorLine:"Unified Assurance · MAOS · AVA · UIM · OSM · FlowOne · Remedy · ServiceNow · AUTIN",
   desc:"Above the per-layer element managers sit OSS functions that work across every layer: correlating alarms into service problems, measuring customer experience with probes, keeping the inventory of sites and cells, activating services ordered by BSS, and running incidents and planned changes.",
   vendors:{ Huawei:"MAOS / SmartCare, SEQ Analyst", Nokia:"MantaRay SON, AVA, FlowOne", Ericsson:"Expert Analytics, Adaptive Inventory, Dynamic Orchestration", Amdocs:"Network / Resource Inventory, Service & Network Automation", Oracle:"Unified Assurance, UIM, OSM", Others:"Remedy, ServiceNow, AUTIN, NetScout" },
   oss:["Spans every network layer"],
   dataT:[["Service problems, root cause","REST / Kafka","API"],["Per-subscriber QoE xDRs","Parquet / Kafka","Stream"],["Sites, cells, links","Inventory tables","Table"],["Incidents, changes","Remedy / ServiceNow tables and REST","Table"]],
   tmf:["ServiceProblem","ServiceLevelObjective","ServiceOrder","TroubleTicket (network)","ChangeRequest","WorkOrder"],
   ai:["Root cause and impact already correlated across layers","QoE per subscriber: the experience the customer actually had","Write-back target: worklogs on network incidents"],
   tab:"oss" }
];

const AI_STAGES = [
 { id:"src", n:"1", title:"Sources", sub:"BSS · OSS · NSS",
   items:["<b>Table</b>: CRM, billing, KPI warehouse, inventory","<b>File</b>: PM XML, CDRs, CM exports, bill runs","<b>API</b>: TMF Open APIs, Remedy, RESTCONF","<b>Stream</b>: alarms, mobility events, Kafka topics"] },
 { id:"ing", n:"2", title:"Ingest & integrate", sub:"Staging server (DMZ)",
   items:["SFTP pull and decode: ASN.1 CDRs, 3GPP XML","Replica / CDC reads from BSS databases","Proxy API: reads, plus worklog write-back","Alarm stream forwarder with buffer and retry","Masking and scope filter at source"] },
 { id:"tmf", n:"3", title:"Normalise to TMF", sub:"Silver layer",
   items:["CDRs → Usage (TMF635), alarms → Alarm (TMF642)","Counters → PerformanceMeasurement (TMF628)","CRM → Customer, Product (TMF629, TMF637)","Identity: IMSI ↔ MSISDN ↔ customer_id","Cell ↔ subscriber map: home cell + time window"] },
 { id:"gold", n:"4", title:"Golden data & features", sub:"Gold layer",
   items:["Customer golden table, one row per subscriber, daily","Cell-day KPI table (pre-aggregated PM)","Feature windows: current vs prior 30 days, cohort z-scores","Search index over runbooks, tickets, TMF and 3GPP specs"] },
 { id:"ai", n:"5", title:"Intelligence", sub:"Rules · models · agents",
   items:["Deterministic scan of the whole base (cheap, auditable)","Registered ML models: churn score, anomaly, forecasts","LLM agents on the shortlist only, with tools to query data and TMF APIs","Explanations cite evidence; no invented probabilities"] },
 { id:"act", n:"6", title:"Act & write back", sub:"Back into BSS / OSS",
   items:["Worklog or ticket via TMF621 (proxy write-back)","Retention / upsell offer via TMF680 → campaign","NOC alert linked to the service problem (TMF656)","Care agent summary at the next contact"] }
];

const LATENCY = [
 ["Seconds","Streams","Alarms, mobility and policy events → real-time correlation and outage impact"],
 ["15 minutes","Micro-batch files","PM counters, CDR batches → cell KPIs and usage aggregates"],
 ["Daily","Batch","Golden table refresh → whole-base scans and agent runs"]
];

const TRACE = [
 { layer:"atx", time:"13:41", sys:"iMaster NCE", mode:"Stream", ent:"ServiceProblem", title:"Microwave backhaul fails",
   text:"Link MW-RYD-0421-0388 between sites RYD-0421 and RYD-0388 raises MW_RDI and goes down.",
   ai:"Root-cause analysis ranks this link above the cell alarm that follows: the cell went down because its backhaul did." },
 { layer:"ran", time:"13:42", sys:"Ericsson ENM (FM)", mode:"Stream", ent:"Alarm", title:"Home cell goes down",
   text:"Cell RYD-0421-L18-1 raises Cell Unavailable (critical). The alarm forwarder pushes it to staging within seconds; it clears at 15:09.",
   ai:"Every subscriber whose home cell is RYD-0421-L18-1 gets an open outage window: 1.5 hours on this day." },
 { layer:"pcore", time:"13:42 – 14:31", sys:"MME events · PGW CDRs · PCF", mode:"File", ent:"Usage", title:"The core sees the impact",
   text:"The MME rejects service requests (eNB_NOT_AVAILABLE), PGW CDRs show data volume falling, and at 14:31 the PCF throttles the line after the fair-usage limit is reached.",
   ai:"Two causes are kept apart: a network outage and a policy throttle. A decline caused by throttling is not a radio fault." },
 { layer:"bss", time:"4 – 5 Nov", sys:"Care · Nimbus app", mode:"API", ent:"TroubleTicket (customer)", title:"The customer reacts",
   text:"Complaint CS-240983 (call drops at home, third contact in 30 days) and a visit to the cancel-line page.",
   ai:"Care and digital intent raise priority. With port-out and contract end, these are the strongest churn signals." },
 { stage:"tmf", time:"Every 15 min / daily", sys:"Staging → TMF layer → golden table", ent:"Usage", title:"Normalised and joined",
   text:"CDRs become Usage, alarms become Alarm, the complaint a TroubleTicket. IMSI 001011234567890 resolves to customer C-100245, and the home cell connects the OSS facts to that customer.",
   ai:"Golden row: data 4.1 GB vs 12.3 GB (−67%), home-cell outage 1.5 h, fair-usage flag true, QoE change −18.2." },
 { stage:"ai", time:"Daily run", sys:"Scan → model → agent", ent:"Customer", title:"Shortlisted and explained",
   text:"The whole-base scan flags the decline, the registered churn model scores the customer, and an LLM agent reads the evidence through tools and writes the explanation with sources.",
   ai:"Likely factors: outage on the home cell plus fair-usage throttling. The agent reports evidence; it does not invent a churn probability." },
 { stage:"act", time:"Same day", sys:"Proxy API write-back · campaign", ent:"Recommendation", title:"Action and write-back",
   text:"A worklog is appended to network incident INC000012351, a retention offer waits for approval, and care sees a summary on the next contact.",
   ai:"Every write-back is logged. Customer-facing offers need human approval." }
];

const CHANNELS = ["Nimbus app","Retail stores","Call centre","Enterprise portal","Partners / MVNO"];
const IFACES = [
 ["⇅","Charging","CHF / OCS ↔ SMF / PGW (Nchf, Gy)"],
 ["↑","Usage","CDRs → mediation → billing (TMF635)"],
 ["↓","Orders","TMF622 → TMF641 → UDM / PCF activation"],
 ["↑","Incidents","Network tickets → care (TMF621)"]
];

function layerById(id){ return LAYERS.find(l => l.id === id); }
function stageTitle(id){ const s = AI_STAGES.find(x => x.id === id); return s ? s.n + " · " + s.title : id; }

function lChips(list){ return list.map(c => `<span class="lchip">${esc(c)}</span>`).join(""); }

function bandHTML(l){
  return `<div class="lband t-${l.tone}${state.layer === l.id ? " sel" : ""}" data-layer="${l.id}" role="button" tabindex="0" aria-pressed="${state.layer === l.id}">
    <div class="lt"><b>${l.title}</b><span>${l.sub}</span></div>
    <div class="lchips">${lChips(l.chips)}</div>
    <div class="lvend">${esc(l.vendorLine)}</div></div>`;
}

function rowHTML(l){
  const sel = state.layer === l.id ? " sel" : "";
  const attrs = `data-layer="${l.id}" role="button" tabindex="0" aria-pressed="${state.layer === l.id}"`;
  return `<div class="lrow t-${l.tone}${sel}" ${attrs}>
      <div class="lt"><b>${l.title}${l.nss ? ' <span class="nsstag">NSS</span>' : ""}</b><span>${l.sub}</span></div>
      <div class="lchips">${lChips(l.chips)}</div></div>
    <div class="losscell${sel}" data-layer="${l.id}"><span class="mini">${esc(l.ossNote)}</span>${l.oss.map(o => `<span class="ossname">${esc(o)}</span>`).join("")}</div>
    <div class="ldata${sel}" data-layer="${l.id}">${l.data.map(([d, m]) => `<span class="ditem"><span class="dc ${m}">${m}</span>${esc(d)}</span>`).join("")}</div>`;
}

function detailHTML(){
  const l = layerById(state.layer); if (!l) return "";
  const tabName = { bss:"BSS", oss:"OSS", nss:"NSS / core" }[l.tab];
  return `<div class="ldetail t-${l.tone}" id="ldetail">
    <div class="ldh"><div><div class="eyebrow">Selected layer</div><h3>${l.title} <span class="lsub">${l.sub}</span>${l.nss ? ' <span class="nsstag">NSS</span>' : ""}</h3></div>
      <a class="act" href="#${l.tab}">Open ${tabName} systems →</a></div>
    <p class="ldesc">${esc(l.desc)}</p>
    <div class="ldgrid">
      <div><h4>Vendor products</h4><dl class="vend">${Object.entries(l.vendors).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
        <h4>Managed by</h4><p class="small">${l.oss.map(esc).join(" · ")}</p></div>
      <div><h4>Data it produces</h4>
        <div class="tblwrap"><table class="stbl ltbl"><thead><tr><th>Data</th><th>Format</th><th>Mode</th></tr></thead>
        <tbody>${l.dataT.map(r => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td><span class="dc ${r[2]}">${r[2]}</span></td></tr>`).join("")}</tbody></table></div></div>
      <div><h4>TMF entities</h4><div class="lents">${l.tmf.map(n => `<button type="button" class="lent" data-lent="${encodeURIComponent(n)}"><span class="dombadge ${domOf(n)}">${domOf(n)}</span>${esc(n)}</button>`).join("")}</div>
        <h4>What the AI stack uses it for</h4><ul class="lai">${l.ai.map(a => `<li>${esc(a)}</li>`).join("")}</ul></div>
    </div></div>`;
}

function layersHTML(){
  if (!state.layer) state.layer = "pcore";
  const rows = LAYERS.filter(l => !l.band);
  const topo = `<div class="topo">
    <div class="lband t-chan"><div class="lt"><b>Customers & channels</b><span>Where people interact</span></div><div class="lchips">${lChips(CHANNELS)}</div></div>
    ${bandHTML(layerById("bss"))}
    <div class="ifaces">${IFACES.map(i => `<span class="iface"><b>${i[0]} ${i[1]}</b>${esc(i[2])}</span>`).join("")}</div>
    <div class="colhd c1"><span style="color:var(--oss)">OSS</span> · manages each layer</div>
    <div class="colhd c2">Network topology · traffic flows from the device to the internet</div>
    <div class="colhd c3">Data emitted · delivery mode</div>
    ${rows.map(rowHTML).join("")}
    ${bandHTML(layerById("oss"))}
    <div class="lband t-stage"><div class="lt"><b>Integration</b><span>Staging server (DMZ)</span></div>
      <div class="lchips">${lChips(["Scheduled file exports","Proxy API · read + write-back","Alarm stream forwarder","Buffer & retry","Masking & scope control"])}</div>
      <div class="lvend">Single controlled point: the AI platform never reaches a source system directly ↓</div></div>
  </div>`;

  const stages = `<div class="aistack">${AI_STAGES.map(s => `<div class="stage" id="stage-${s.id}">
      <div class="sh">Step ${s.n}</div><h4>${s.title}</h4><div class="ssub">${s.sub}</div>
      ${s.id === "src" ? `<div class="srcdoms"><span class="dombadge BSS">BSS</span><span class="dombadge OSS">OSS</span><span class="dombadge NSS">NSS</span></div>` : ""}
      <ul>${s.items.map(i => `<li>${i}</li>`).join("")}</ul></div>`).join("")}</div>
    <div class="gov"><b>Governance across every step</b><span>Consent and data-protection rules (KSA PDPL, India DPDP) gate location, call graph and credit data</span><span>Masking at source</span><span>Audit log of every read and write-back</span><span>Model registry and versions</span><span>Human approval for customer-facing actions</span></div>
    <div class="lat">${LATENCY.map(t => `<div><b>${t[0]}</b><span class="mini">${t[1]}</span><span>${t[2]}</span></div>`).join("")}</div>`;

  const trace = `<ol class="trace">${TRACE.map((t, i) => {
      const where = t.layer
        ? `<button type="button" class="where" data-goto-layer="${t.layer}">${layerById(t.layer).title}</button>`
        : `<button type="button" class="where ai" data-goto-stage="${t.stage}">AI stack · ${stageTitle(t.stage)}</button>`;
      return `<li><span class="tn">${i + 1}</span><div class="tb">
        <div class="tmeta">${where}<span class="ttime">${esc(t.time)}</span><span>${esc(t.sys)}</span>${t.mode ? `<span class="dc ${t.mode}">${t.mode}</span>` : ""}</div>
        <b class="ttitle">${esc(t.title)}</b><p>${esc(t.text)}</p>
        <p class="tai"><span>AI stack:</span> ${esc(t.ai)}</p>
        <button type="button" class="lent" data-lent="${encodeURIComponent(t.ent)}"><span class="dombadge ${domOf(t.ent)}">${domOf(t.ent)}</span>${esc(t.ent)}</button></div></li>`; }).join("")}</ol>`;

  return `<section id="layers">
    <div class="shead"><h2>Data layer</h2></div>
    <p class="sub">Where BSS, OSS and NSS sit around the network, what each layer emits, and how the AI stack turns that data into explanations and actions. Select any layer to see its products, data and TMF entities.</p>
    <h3 class="parth">Topology and system positions</h3>
    ${topo}
    ${detailHTML()}
    <h3 class="parth" id="aistack-h">How the AI stack processes the data</h3>
    ${stages}
    <h3 class="parth">One signal, end to end</h3>
    <p class="sub">The sample customer C-100245 through every layer: from a microwave failure to a worklog and a retention offer. Select a layer or step to see it in the diagrams above.</p>
    ${trace}
  </section>`;
}

function selectLayer(id, scrollTo){
  state.layer = id; render();
  const el = document.querySelector(scrollTo === "row" ? `.lrow[data-layer="${id}"], .lband[data-layer="${id}"]` : "#ldetail");
  if (el) el.scrollIntoView({ block: scrollTo === "row" ? "center" : "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  const f = document.querySelector(`.lrow[data-layer="${id}"], .lband[data-layer="${id}"]`); if (f && scrollTo !== "row") f.focus({ preventScroll: true });
}

document.getElementById("main").addEventListener("click", e => {
  const lent = e.target.closest("[data-lent]");
  if (lent) { const n = decodeURIComponent(lent.dataset.lent); openEntity(domOf(n) + "|" + n, lent); return; }
  const gl = e.target.closest("[data-goto-layer]"); if (gl) { selectLayer(gl.dataset.gotoLayer, "row"); return; }
  const gs = e.target.closest("[data-goto-stage]");
  if (gs) { const s = document.getElementById("stage-" + gs.dataset.gotoStage); if (s) { s.scrollIntoView({ block: "center", behavior: "smooth" }); s.classList.remove("flash"); void s.offsetWidth; s.classList.add("flash"); } return; }
  const l = e.target.closest("[data-layer]"); if (l && !e.target.closest("a")) selectLayer(l.dataset.layer, "detail");
});
document.getElementById("main").addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("[data-layer][role=button]")) { e.preventDefault(); selectLayer(e.target.dataset.layer, "detail"); }
});
