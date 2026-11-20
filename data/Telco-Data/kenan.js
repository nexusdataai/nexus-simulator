// "Kenan BP" tab: where Kenan BP 12.0 gets its data (BSS / NSS / external), the format and delivery of each feed,
// the Kenan module that takes it in, the tables it lands in, and the final billing tables.
// Field names, record layouts and module names come from the Kenan BP 12.0 Technical Reference,
// Reports & File Layouts and Database Reference. Sample values are invented and follow the atlas thread
// (customer C-100245 = Kenan account_no 3000245, MSISDN 966591234567 = subscr_no 5004501).
// Uses the page's esc(), hi(), state and sampleHTML().

const KENAN_FEEDS = [
 {sys:"Usage CDRs (voice, SMS, data)", layer:"NSS", from:"MSC / IMS, SMSC, packet gateway (PGW / SMF) → mediation",
  data:"Who (MSISDN), usage type, start time, A- and B-number or cell, duration / volume / count, completion code",
  fmt:"Fixed-width ASCII: HDR header, A01 / B01 / P01 detail records, TRA / TRL trailer; optional .data + .ctrl pair; TE1 / TE2 binary (TXD)",
  del:["File","Table"], dn:"COM pulls the file by FTP, shared folder (NFS) or IPDR",
  intake:"COM → MCAP (route) → CAP (guide + rate) → LTP (load)",
  lands:"FILE_STATUS → CDR_DATA, CDR_UNBILLED, CDR_DATA_TAX, CDR_DATA_DUC, CDR_FREE, CDR_DATA_WORK",
  api:"TMF635", sid:"Usage"},
 {sys:"Real-time usage (Flash mode)", layer:"NSS", from:"Real-time usage generator (switch, IN or charging front end)",
  data:"Same fields as the usage file, one event at a time",
  fmt:"Kenan usage records over a TCP/IP socket into MCAP's IPC message queue",
  del:["Stream"], dn:"Event-time unit credits (ETUC) work in batch mode only",
  intake:"MCAP (Flash mode) → CAP → LTP",
  lands:"CDR_DATA, CDR_UNBILLED",
  api:"TMF635", sid:"Usage"},
 {sys:"Roaming usage (TAP in / out)", layer:"NSS", from:"Roaming clearing house (Syniverse, BICS) and partner operators",
  data:"Our subscribers' usage abroad (incollect); visitors' usage on our network (outcollect)",
  fmt:"TAP3 ASN.1, translated by TIP into Kenan record format",
  del:["File","Table"], intake:"COM → TIP (translate) → MCAP / CAP → LTP",
  lands:"CDR_DATA (incollect), CDR_OUTCOLLECTS (to charge partners)",
  api:"TMF635", sid:"Usage"},
 {sys:"Customers and accounts", layer:"BSS", from:"CRM, CSRs in Customer Center, bulk orders",
  data:"Account, bill name and address, hierarchy (parent / child), bill cycle, currency, payment method, external IDs",
  fmt:"API Transaction Set calls (Tuxedo); Customer Center screens; Bulk Ordering batches",
  del:["API","Table"], intake:"Customer Center / API TS / Bulk Ordering",
  lands:"CMF, EXTERNAL_ID_ACCT_MAP (Catalog DB), CMF_BALANCE",
  api:"TMF629 · TMF666", sid:"Customer, BillingAccount"},
 {sys:"Services and products (orders)", layer:"BSS", from:"Order management, CRM; OSS activation results come back through Orders Services",
  data:"Subscriptions (MSISDN, ICCID), products and packages, contracts, connect / disconnect dates, suspend / resume",
  fmt:"API TS; Orders Services orders and sub-orders (Activator / Expander)",
  del:["API","Table"], intake:"Orders Services / API TS / Customer Center",
  lands:"SERVICE, EXTERNAL_ID_EQUIP_MAP, PRODUCT, contract and unit-credit instance tables",
  api:"TMF622 · TMF637 · TMF641", sid:"ProductOrder, Product, Service"},
 {sys:"Product catalogue and rates", layer:"BSS", from:"Product and pricing team",
  data:"Usage types, recurring and one-off charges, rates, discounts, unit credits, packages, contracts, bill cycles",
  fmt:"Configurable Admin DB tables (_REF / _VALUES pairs + DESCRIPTIONS)",
  del:["Table"], dn:"Replicated from Admin to Customer DBs (REPLICATION_TABLES)",
  intake:"Configurator / FX Configurator",
  lands:"USAGE_TYPES, RATE_USAGE, RATE_RC, PRODUCT_ELEMENTS, NRC_TRANS_DESCR, DISCOUNT_DEFINITIONS, UNIT_CR_DEFINITIONS",
  api:"TMF620", sid:"ProductOffering, ProductOfferingPrice"},
 {sys:"Lockbox (cheque) payments", layer:"EXT", from:"Bank lockbox service",
  data:"Cheques received: amount, bank / account / cheque number, invoice or open item, account external ID",
  fmt:"Fixed-width ASCII, record types 1–9 (file, lockbox, batch, cheque detail, totals)",
  del:["File","Table"], dn:"COM, or modem via CLEO",
  intake:"LBX", lands:"BMF (source_type 0), LBX_ERROR, LBX_POST_DATED",
  api:"TMF676", sid:"Payment"},
 {sys:"Card payments (CPM)", layer:"EXT", from:"Credit-card clearinghouse / payment gateway",
  data:"Charge requests out; approvals, declines and reversals back",
  fmt:"Fixed-width 80-byte send and response files (Record Formats A–F: HD / DT / TR)",
  del:["File","Table"], dn:"Near real-time through Customer Center and API TS since 12.0",
  intake:"CPM (send) ← COM → CPM (receive)", lands:"PAYMENT_TRANS → BMF (source_type 3), CPM_CYCLE_STATUS",
  api:"TMF676 · TMF670", sid:"Payment, PaymentMethod"},
 {sys:"Direct debit (EFT)", layer:"EXT", from:"Bank / direct-debit clearinghouse (e.g. NACHA, CheckFree)",
  data:"Debit requests out; accepted and returned debits back",
  fmt:"Fixed-width 98-byte send and return files (HD / DT / TR)",
  del:["File","Table"], intake:"EFT", lands:"PAYMENT_TRANS → BMF (source_type 2), EFT_CYCLE_STATUS",
  api:"TMF676", sid:"Payment"},
 {sys:"Manual payments, adjustments, one-off charges", layer:"BSS", from:"CSRs in Customer Center; external systems via API TS",
  data:"Counter payments, deposits, credits and debits, disputes, one-off and instalment charges",
  fmt:"Customer Center screens; API TS transactions",
  del:["Table","API"], intake:"Customer Center / API TS",
  lands:"BMF (source_type 1), ADJ, NRC",
  api:"TMF676 · TMF678", sid:"Payment, AppliedCustomerBillingRate"},
 {sys:"Number plan and usage points", layer:"EXT", from:"Numbering authority (LERG in North America; national plan elsewhere); Vertex tax geography",
  data:"Number prefixes, regions, rate centres, international flags, tax geocodes",
  fmt:"LUP files (fixed fields matching USAGE_POINTS); Vertex data files",
  del:["Table"], dn:"Loaded by LOAD_USG_PTS; refreshed for recurring charges by RJU",
  intake:"LOAD_USG_PTS", lands:"USAGE_POINTS, POINT_REGION_REF, ACCESS_REGION_REF, POINT_CLASS_REF",
  api:"TMF673 · TMF674", sid:"GeographicAddress, GeographicSite"},
];

const KENAN_TABLES = [
 ["CMF","Customer","Customer Center / API TS","CRM orders","Account","account_no, parent_id, bill_period, account_type, bill_lname, bill_address1, currency_code, pay_method","Master record every module reads"],
 ["EXTERNAL_ID_ACCT_MAP · EXTERNAL_ID_EQUIP_MAP","Catalog + Customer","Provisioning","Orders","External ID (BA number, MSISDN, ICCID)","external_id, external_id_type, account_no, subscr_no, server_id","How MCAP, LBX and the API find the internal account"],
 ["SERVICE · PRODUCT","Customer","Orders Services / API TS","Orders","Subscription; product instance","subscr_no, parent_account_no, emf_config_id; element_id, product_active_dt","What the customer has, used by CAP and BIP"],
 ["CDR_DATA","Customer","LTP","Usage files via CAP","Rated usage event (written once, never updated)","msg_id, account_no, subscr_no, type_id_usg, trans_dt, point_origin, point_target, primary_units, rated_units, amount","Usage detail; source for bill usage lines"],
 ["CDR_UNBILLED · CDR_BILLED · CDR_RERATED","Customer","LTP · BIP · RAP","CDR_DATA","Pointer per CDR","msg_id, account_no; bill_ref_no + billed_amount (BILLED); old / new msg_id (RERATED)","Unbilled vs billed usage and re-rating audit trail"],
 ["BILL_INVOICE","Customer","BIP","CMF, usage, RC, NRC, ADJ, BMF, discounts, tax","Bill","account_no, bill_ref_no, bill_period, prep_status, format_status, backout_status, jnl_status","Bill header and bill-run status"],
 ["BILL_INVOICE_DETAIL","Customer","BIP","Same as above","Bill line","bill_ref_no, bill_invoice_row, type_code, element_id, units, amount, discount, tax","Every charge, credit and payment on the bill"],
 ["BILL_INVOICE_TAX · BILL_INVOICE_DISCOUNT","Customer","BIP","Tax and discount rules","Tax / discount per bill line","bill_ref_no, bill_invoice_row, tax_type_code, federal / state / other tax; discount_id","Tax and discount breakdown"],
 ["CMF_BALANCE","Customer","BIP, payments","Bills, payments, adjustments","Account per bill","account_no, bill_ref_no, new_charges, total_adj, total_paid, balance_due, dispute_amt","Balance due; Collections reads it"],
 ["BILL_IMAGE","Customer","BIF / Invoice Generator","BILL_INVOICE*","Bill page","account_no, bill_ref_no, bill_date, due_date, page_no, image_type","Formatted bill; BID dispatches it"],
 ["BMF · PAYMENT_TRANS","Customer","LBX, CPM, EFT, Customer Center","Bank and clearinghouse files","Payment; payment request","account_no, trans_date, trans_amount, source_type, bmf_trans_type; tracking_id, trans_status, response_code","Payments received and payment attempts"],
 ["ADJ · NRC","Customer","Customer Center / API TS","CSR actions","Adjustment; one-off charge","account_no, adj_trans_code, total_amt; type_id_nrc, rate, effective_date","Credits, debits, one-off and instalment charges"],
 ["ARM_COLLECTABLE · ARM_HISTORY","Customer","Collections","CMF_BALANCE, payments","Account in collections; action taken","account_no, scenario, threshold, action, status","Dunning and debt follow-up"],
 ["JNL_DETAIL → G/L feed","Customer","JNL","Bills, payments, adjustments, write-offs","Journal line","jnl_ref_no, account_no, bill_ref_no, element_id, jnl_code_id, reported_amount, jnl_feed_status","Revenue and tax into the general ledger"],
];
const KENAN_TABLE_SAMPLES = {"BILL_INVOICE":1,"BILL_INVOICE_DETAIL":1,"CMF_BALANCE":1,"ARM_COLLECTABLE · ARM_HISTORY":1,"JNL_DETAIL → G/L feed":1};

const KENAN_FLOW = [
 ["NSS","Network + mediation",["COM","MCAP","CAP","LTP"],"CDR_DATA · CDR_UNBILLED"],
 ["BSS","CRM, orders, CSRs",["Customer Center","API TS","Orders Services"],"CMF · SERVICE · PRODUCT"],
 ["BSS","Product team",["Configurator"],"RATE_* · USAGE_TYPES (Admin DB)"],
 ["—","Bill cycle",["BIP","BIF / IGEN","BID"],"BILL_INVOICE* · CMF_BALANCE · BILL_IMAGE"],
 ["EXT","Banks, card + debit clearinghouses",["COM","LBX / CPM / EFT"],"BMF · PAYMENT_TRANS"],
 ["—","Overdue balances",["Collections"],"ARM_* (dunning)"],
 ["—","All money movements",["JNL"],"JNL_DETAIL → G/L file"],
];

const KENAN_NOTES = [
 ["Three databases","Catalog (one) maps external IDs to account_no and the Customer DB that holds them. Admin (one) holds products, rates and settings. Customer (one or more) holds accounts, usage, bills and payments; everything for one account hierarchy sits on one Customer DB."],
 ["OSS has no direct feed","Kenan does not read alarms, performance or inventory. OSS only appears through order fulfilment: Orders Services hands service orders to activation and records the result."],
 ["Usage arrives already mediated","Kenan expects normalised records. Raw switch CDRs (ASN.1) are converted by mediation, or by TIP for TAP, before MCAP sees them. RAW_USAGE_FIELD_MAPPING maps each record format to CDR columns."],
 ["CDR_DATA is insert-only","Re-rating (RAP) never updates a CDR. It writes a new row and links old and new in CDR_RERATED; billed status is tracked by pointer tables."],
 ["Amounts have implied decimals","Money fields are integers in minor units (29900 = 299.00) using the currency's implied_decimal setting."],
 ["Everything is scheduled in tables","Every module instance (cap01, bip01 …) is a PROCESS_SCHED row and reports status in PROCESS_STATUS; Operations Center writes these rows."],
 ["Find your real sources","EXT_SOURCE_ID_REF, EXT_CONTACTS and EXT_FTP_ACCESS list the external systems your Kenan actually exchanges files with; FILE_STATUS shows every file received."],
];
Object.assign(window.SAMPLES = window.SAMPLES || {}, {
 "Usage CDRs (voice, SMS, data)": {
  "File": {
   "name": "MSC1_USG_20261113220000.dat",
   "note": "Fixed-width Kenan usage file: HDR + A01 detail (415 bytes) + TRA. Positions follow Reports & File Layouts, tables 4, 5 and 7",
   "content": "HDR2026111322000004150000006MEDIATION       5.2                 \nA01MSC1-0000881245                                          00101     1966591234567                                    20261113184502              003966501112233    966591234567    0000000184                                                                                                                                                                                                                            001\nA01MSC1-0000881301                                          00102     1966591234567                                    20261113191030              003971501234567    966591234567    0000000425                                                                                                                                                                                                                            001\nA01SMSC-0045519920                                          00201     1966591234567                                    20261113192211              003966551239876    966591234567    0000000001                                                                                                                                                                                                                            001\nA01PGW2-7781220931     pgw2;1699901100;77812209             00301     1966591234567                                    20261113200000              003internet        RYD-0421-L18-1  0734003200                                                                                                                                                                                                                            001\nA01MSC1-0000881422                                          00101     1966591234568                                    20261113203315              003966591230000    966591234568    0000000062                                                                                                                                                                                                                            001\nA01MSC1-0000881499                                          00101     1966591234570                                    20261113210041              003966500000000    966591234570    0000000012                                                                                                                                                                                                                            002\nTRA2026111322000004150000006MEDIATION       5.2                 \n"
  },
  "Table": {
   "name": "CDR_DATA (+ CDR_UNBILLED pointer)",
   "src": "Customer DB, written by LTP after CAP rates the file. Amounts in minor units (implied 2 decimals)",
   "cols": [
    "msg_id",
    "account_no",
    "subscr_no",
    "type_id_usg",
    "trans_dt",
    "point_origin",
    "point_target",
    "primary_units",
    "rated_units",
    "amount",
    "file_id",
    "in CDR_UNBILLED"
   ],
   "rows": [
    [
     "90881245",
     "3000245",
     "5004501",
     "101",
     "2026-11-13 18:45:02",
     "966591234567",
     "966501112233",
     "184",
     "4",
     "120",
     "77120",
     "yes"
    ],
    [
     "90881301",
     "3000245",
     "5004501",
     "102",
     "2026-11-13 19:10:30",
     "966591234567",
     "971501234567",
     "425",
     "8",
     "1680",
     "77120",
     "yes"
    ],
    [
     "90881302",
     "3000245",
     "5004501",
     "201",
     "2026-11-13 19:22:11",
     "966591234567",
     "966551239876",
     "1",
     "1",
     "25",
     "77120",
     "yes"
    ],
    [
     "90881303",
     "3000245",
     "5004501",
     "301",
     "2026-11-13 20:00:00",
     "RYD-0421-L18-1",
     "internet",
     "734003200",
     "700",
     "0",
     "77120",
     "yes (in bundle)"
    ],
    [
     "90881422",
     "3000246",
     "5004502",
     "101",
     "2026-11-13 20:33:15",
     "966591234568",
     "966591230000",
     "62",
     "2",
     "0",
     "77120",
     "yes"
    ]
   ]
  }
 },
 "Real-time usage (Flash mode)": {
  "Stream": {
   "topic": "MCAP socket · IPC message queue",
   "proto": "TCP/IP socket (Flash mode), one Kenan usage record per message, shown as JSON",
   "events": [
    {
     "ts": "2026-11-14 09:01:12",
     "key": "966591234567",
     "v": {
      "rec": "A01",
      "type_id_usg": 101,
      "trans_dt": "20261114090112",
      "point_target": "966501112233",
      "primary_units": 96,
      "comp_status": 1
     }
    },
    {
     "ts": "2026-11-14 09:01:40",
     "key": "966591234567",
     "v": {
      "rec": "A01",
      "type_id_usg": 201,
      "trans_dt": "20261114090140",
      "point_target": "966551239876",
      "primary_units": 1,
      "comp_status": 1
     }
    },
    {
     "ts": "2026-11-14 09:02:05",
     "key": "966591234568",
     "v": {
      "rec": "A01",
      "type_id_usg": 301,
      "trans_dt": "20261114090205",
      "point_target": "internet",
      "primary_units": 52428800,
      "comp_status": 1
     }
    },
    {
     "ts": "2026-11-14 09:02:31",
     "key": "966591234570",
     "v": {
      "rec": "A01",
      "type_id_usg": 101,
      "trans_dt": "20261114090231",
      "point_target": "966500000000",
      "primary_units": 0,
      "comp_status": 2
     }
    }
   ]
  }
 },
 "Roaming usage (TAP in / out)": {
  "File": {
   "name": "in.A01.AREEI.20261114030500.data",
   "note": "TAP3 file from the clearing house, translated by TIP into Kenan A01 records (TIP output naming: task.record_type.output_value.datetime.data)",
   "content": "HDR2026111403050004150000002TIP             12.0                \nA01TAP-AREEI-000118                                         00401     1966591234567                                    20261110093012              004internet        AREEI-CELL-304180440401920                                  00901                                                                     Roaming data, UAE (etisalat)                                                                                    001\nA01TAP-AREEI-000119                                         00402     1966591234567                                    20261110101544              004971501234567    966591234567    0000000312                                  00901                                                                     Roaming voice MO, UAE                                                                                           001\nTRA2026111403050004150000002TIP             12.0                \n"
  },
  "Table": {
   "name": "CDR_OUTCOLLECTS",
   "src": "Customer DB. Visiting roamers' usage on our network, kept to charge the partner operator",
   "cols": [
    "msg_id",
    "provider_id",
    "type_id_usg",
    "trans_dt",
    "external_id (IMSI)",
    "primary_units",
    "amount",
    "tap_file_out"
   ],
   "rows": [
    [
     "91002217",
     "901",
     "401",
     "2026-11-12 14:22:10",
     "424020000123456",
     "104857600",
     "0",
     "CDSAUSTAREEI01234"
    ],
    [
     "91002218",
     "901",
     "402",
     "2026-11-12 15:03:44",
     "424020000123456",
     "185",
     "1110",
     "CDSAUSTAREEI01234"
    ],
    [
     "91002290",
     "915",
     "402",
     "2026-11-12 16:41:09",
     "602021234567890",
     "60",
     "360",
     "CDSAUSTEGYVF00871"
    ]
   ]
  }
 },
 "Customers and accounts": {
  "Table": {
   "name": "CMF (customer master file)",
   "src": "Customer DB; external IDs live in EXTERNAL_ID_ACCT_MAP (Catalog DB)",
   "cols": [
    "account_no",
    "external_id (type 1)",
    "parent_id",
    "account_type",
    "account_category",
    "bill_lname / bill_company",
    "bill_city",
    "bill_period",
    "currency_code",
    "pay_method",
    "bill_disp_meth"
   ],
   "rows": [
    [
     "3000245",
     "BA-7781203",
     "",
     "1",
     "10",
     "Al-Harbi",
     "Riyadh",
     "M14",
     "682",
     "2 (card)",
     "2 (e-bill)"
    ],
    [
     "3000246",
     "BA-7781204",
     "",
     "1",
     "10",
     "Al-Qahtani",
     "Jeddah",
     "M01",
     "682",
     "1 (cash)",
     "1 (paper)"
    ],
    [
     "3000247",
     "BA-7781205",
     "3000200",
     "2",
     "20",
     "Al-Rashid Trading Co.",
     "Dammam",
     "M14",
     "682",
     "3 (direct debit)",
     "2 (e-bill)"
    ],
    [
     "3000248",
     "BA-7781206",
     "",
     "1",
     "10",
     "Al-Shehri",
     "Riyadh",
     "M20",
     "682",
     "3 (direct debit)",
     "1 (paper)"
    ]
   ]
  },
  "API": {
   "method": "CALL",
   "path": "API TS · Account create (Tuxedo service, from CRM / Customer Center)",
   "src": "Kenan FX API Transaction Set; fields shown as JSON for reading",
   "body": {
    "account": {
     "account_type": 1,
     "account_category": 10,
     "bill_lname": "Al-Harbi",
     "bill_fname": "Faisal",
     "bill_address1": "King Fahd Rd 1201",
     "bill_city": "Riyadh",
     "bill_country_code": 682,
     "bill_period": "M14",
     "currency_code": 682,
     "language_code": 1,
     "pay_method": 2
    },
    "external_ids": [
     {
      "external_id": "BA-7781203",
      "external_id_type": 1
     },
     {
      "external_id": "C-100245",
      "external_id_type": 7
     }
    ],
    "result": {
     "account_no": 3000245,
     "server_id": 3
    }
   }
  }
 },
 "Services and products (orders)": {
  "Table": {
   "name": "SERVICE · EXTERNAL_ID_EQUIP_MAP · PRODUCT",
   "src": "Customer DB. One subscription and the products on it",
   "cols": [
    "subscr_no",
    "external_id",
    "external_id_type",
    "parent_account_no",
    "emf_config_id",
    "element_id (product)",
    "product_active_dt",
    "product_inactive_dt"
   ],
   "rows": [
    [
     "5004501",
     "966591234567",
     "9 (MSISDN)",
     "3000245",
     "10 (GSM)",
     "1299 Postpaid 299 MRC",
     "2024-08-14",
     ""
    ],
    [
     "5004501",
     "966591234567",
     "9 (MSISDN)",
     "3000245",
     "10 (GSM)",
     "1310 StreamPlus add-on",
     "2026-06-02",
     ""
    ],
    [
     "5004501",
     "8996601234567890123",
     "11 (ICCID)",
     "3000245",
     "10 (GSM)",
     "—",
     "2024-08-14",
     ""
    ],
    [
     "5004502",
     "966591234568",
     "9 (MSISDN)",
     "3000246",
     "10 (GSM)",
     "1250 Prepaid base",
     "2026-03-02",
     ""
    ]
   ]
  },
  "API": {
   "method": "CALL",
   "path": "Orders Services · order 'Add service' (API TS → Activator / Expander)",
   "src": "Order with sub-orders; shown as JSON",
   "body": {
    "order_id": "ORD-26-0091822",
    "account_no": 3000245,
    "suborders": [
     {
      "type": "SERVICE_ADD",
      "emf_config_id": 10,
      "external_ids": [
       {
        "id": "966591234567",
        "type": 9
       }
      ]
     },
     {
      "type": "PRODUCT_ADD",
      "element_id": 1310,
      "active_dt": "2026-06-02"
     }
    ],
    "status": "COMMITTED"
   }
  }
 },
 "Product catalogue and rates": {
  "Table": {
   "name": "RATE_RC · USAGE_TYPES · RATE_USAGE",
   "src": "Admin DB configurable tables, edited in Configurator / FX Configurator and replicated to Customer DBs",
   "cols": [
    "table",
    "key",
    "description",
    "rate / rule",
    "currency",
    "active_date"
   ],
   "rows": [
    [
     "RATE_RC",
     "element_id 1299, billing_frequency M",
     "Postpaid 299 monthly fee",
     "29900",
     "682 (SAR)",
     "2024-01-01"
    ],
    [
     "RATE_RC",
     "element_id 1310, billing_frequency M",
     "StreamPlus add-on",
     "3000",
     "682",
     "2025-05-01"
    ],
    [
     "USAGE_TYPES",
     "type_id_usg 101",
     "National voice",
     "per 60 s, round up",
     "682",
     "2024-01-01"
    ],
    [
     "RATE_USAGE",
     "type_id_usg 102, jurisdiction ARE",
     "International voice to UAE",
     "210 per minute",
     "682",
     "2026-01-01"
    ],
    [
     "RATE_USAGE",
     "type_id_usg 301",
     "Domestic data",
     "0 inside bundle, 50 per MB out",
     "682",
     "2024-01-01"
    ]
   ]
  }
 },
 "Lockbox (cheque) payments": {
  "File": {
   "name": "LBX_RIYADHBANK_20261118.txt",
   "note": "Fixed-width lockbox file: types 1, 2, 5, 6, 7, 8, 9 (Reports & File Layouts, chapter 5). Type 6 shown up to the External ID field",
   "content": "1STARTEL   RIYADHBANK2611180615000044715M\n2RIYADHBANKLBX0042\n5001LBX0042261118RIYADHBANK00001\n6001000001000000000000034385080000123           1022334455          000771    C3000245-26          00000000000003438500000000000003438500000000000000000000BA-7781203\n6001000002000000000000241250080000456           2099887766          004512    C3000247-26          00000000000024125000000000000024125000000000000000000000BA-7781205\n7001LBX0042261118000002000000000000275635\n8LBX0042261118000000002000000000000275635001\n90000000008\n"
  },
  "Table": {
   "name": "BMF (payments)",
   "src": "Customer DB; source_type 0 = lockbox",
   "cols": [
    "account_no",
    "tracking_id",
    "trans_date",
    "trans_amount",
    "source_type",
    "micr_check_num",
    "bill_ref_no",
    "file_id"
   ],
   "rows": [
    [
     "3000245",
     "8812001",
     "2026-11-18",
     "34385",
     "0 (LBX)",
     "000771",
     "226001245",
     "88104"
    ],
    [
     "3000247",
     "8812002",
     "2026-11-18",
     "241250",
     "0 (LBX)",
     "004512",
     "226001247",
     "88104"
    ]
   ]
  }
 },
 "Card payments (CPM)": {
  "File": {
   "name": "CPM_SEND_20261119.dat + CPM_RESP_20261119.dat",
   "saveAs": "cpm_send_and_response.txt",
   "note": "80-byte Record Format A: HD header, DT detail, TR trailer. Second block is the clearinghouse response (0051 = declined)",
   "content": "HD000412345678M771KENANSYS  261119020000CCSEND01                                \nDT4111XXXXXXXX111108282000000000000034385261119            CPM0000000455010000  \nDT5500XXXXXXXX000401272000000000000057485261119            CPM0000000455020000  \nTR00000002000000000000091870                                                    \nHD000412345678M771MADAHUB   261119061500CCSEND01                                \nDT4111XXXXXXXX111108282000000000000034385261119A81F22261119CPM0000000455010000  \nDT5500XXXXXXXX000401272000000000000057485261119            CPM0000000455020051  \nTR00000002000000000000091870                                                    \n"
  },
  "Table": {
   "name": "PAYMENT_TRANS",
   "src": "Customer DB; CPM writes requests and responses, accepted ones become BMF rows",
   "cols": [
    "account_no",
    "tracking_id",
    "amount",
    "trans_type",
    "trans_status",
    "response_code",
    "ccauth_code",
    "trans_date"
   ],
   "rows": [
    [
     "3000245",
     "CPM000000045501",
     "34385",
     "2 (debit)",
     "accepted",
     "0000",
     "A81F22",
     "2026-11-19"
    ],
    [
     "3000249",
     "CPM000000045502",
     "57485",
     "2 (debit)",
     "declined",
     "0051",
     "",
     "2026-11-19"
    ]
   ]
  }
 },
 "Direct debit (EFT)": {
  "File": {
   "name": "EFT_SEND_20261120.dat",
   "note": "98-byte Record Format A: HD header, DT detail (bank code, account, amount), TR trailer",
   "content": "HD000412345678M771KENANSYS  261120050000EFTSEND1                                                  \nDT1080000123SA448000012345678901000000000000057485AL RAJHI BANK         261120EFT0000000311070000 \nDT1080000999SA038000098765432109000000000000057485ALINMA BANK           261120EFT0000000311080000 \nTR00000002000000000000114970                                                                      \n"
  },
  "Table": {
   "name": "PAYMENT_TRANS",
   "src": "Customer DB; EFT_CYCLE_STATUS tracks each send / return cycle",
   "cols": [
    "account_no",
    "tracking_id",
    "amount",
    "trans_status",
    "response_code",
    "trans_date"
   ],
   "rows": [
    [
     "3000248",
     "EFT000000031107",
     "57485",
     "returned",
     "R01 insufficient funds",
     "2026-11-20"
    ],
    [
     "3000250",
     "EFT000000031108",
     "57485",
     "accepted",
     "0000",
     "2026-11-20"
    ]
   ]
  }
 },
 "Manual payments, adjustments, one-off charges": {
  "Table": {
   "name": "BMF · ADJ · NRC",
   "src": "Customer DB, entered by CSRs in Customer Center or via API TS",
   "cols": [
    "table",
    "account_no",
    "tracking_id",
    "type",
    "amount",
    "date",
    "note"
   ],
   "rows": [
    [
     "BMF",
     "3000246",
     "8812090",
     "manual payment (source_type 1)",
     "20000",
     "2026-11-15",
     "Paid at Jeddah store"
    ],
    [
     "ADJ",
     "3000247",
     "5520114",
     "adj_trans_code 210 goodwill credit",
     "-5000",
     "2026-11-02",
     "Outage credit"
    ],
    [
     "NRC",
     "3000245",
     "6610032",
     "type_id_nrc 405 SIM replacement",
     "2500",
     "2026-11-08",
     "SIM swap"
    ],
    [
     "NRC",
     "3000245",
     "6610033",
     "type_id_nrc 510 device instalment 7/24",
     "12500",
     "2026-11-14",
     "Installment NRC"
    ]
   ]
  },
  "API": {
   "method": "CALL",
   "path": "API TS · Adjustment create",
   "src": "Same transaction Customer Center uses; shown as JSON",
   "body": {
    "account_no": 3000247,
    "adj_trans_code": 210,
    "total_amt": -5000,
    "annotation": "Outage credit, ticket TT-88120",
    "request_status": "approved",
    "supervisor_name": "m.alotaibi"
   }
  }
 },
 "Number plan and usage points": {
  "Table": {
   "name": "USAGE_POINTS · POINT_REGION_REF",
   "src": "Admin DB, loaded from LUP files by LOAD_USG_PTS (LERG in North America; national numbering plan elsewhere)",
   "cols": [
    "point_id",
    "point",
    "point_region",
    "point_class",
    "country_code",
    "is_international",
    "point_city"
   ],
   "rows": [
    [
     "40021",
     "96650",
     "KSA-MOB",
     "2 (mobile)",
     "682",
     "0",
     "Saudi mobile"
    ],
    [
     "40022",
     "96611",
     "KSA-RYD",
     "1 (fixed)",
     "682",
     "0",
     "Riyadh"
    ],
    [
     "51007",
     "97150",
     "ARE-MOB",
     "2 (mobile)",
     "784",
     "1",
     "UAE mobile"
    ]
   ]
  }
 },
 "BILL_INVOICE": {
  "Table": {
   "name": "BILL_INVOICE",
   "src": "Customer DB, one row per bill (BIP). Amounts live in BILL_INVOICE_DETAIL and CMF_BALANCE",
   "cols": [
    "account_no",
    "bill_ref_no",
    "bill_period",
    "statement date",
    "prep_status",
    "format_status",
    "backout_status",
    "jnl_status",
    "interim_bill_flag"
   ],
   "rows": [
    [
     "3000245",
     "226001245",
     "M14",
     "2026-11-14",
     "1 (done)",
     "2 (formatted)",
     "0",
     "1",
     "0"
    ],
    [
     "3000247",
     "226001247",
     "M14",
     "2026-11-14",
     "1 (done)",
     "2 (formatted)",
     "0",
     "1",
     "0"
    ],
    [
     "3000248",
     "226001290",
     "M20",
     "2026-10-20",
     "1 (done)",
     "2 (formatted)",
     "0",
     "1",
     "0"
    ]
   ]
  }
 },
 "BILL_INVOICE_DETAIL": {
  "Table": {
   "name": "BILL_INVOICE_DETAIL",
   "src": "Customer DB, one row per bill line. type_code: 1 payment, 2 recurring, 3 one-off, 4 adjustment, 6 unit credit, 7 usage",
   "cols": [
    "bill_ref_no",
    "bill_invoice_row",
    "type_code",
    "element_id / type",
    "units",
    "amount",
    "discount",
    "tax"
   ],
   "rows": [
    [
     "226001245",
     "1",
     "2 (RC)",
     "1299 Postpaid 299",
     "1",
     "29900",
     "0",
     "4485"
    ],
    [
     "226001245",
     "2",
     "7 (usage)",
     "102 Intl voice UAE",
     "8",
     "1680",
     "0",
     "252"
    ],
    [
     "226001245",
     "3",
     "7 (usage)",
     "301 Data",
     "700",
     "0",
     "0",
     "0"
    ],
    [
     "226001245",
     "4",
     "1 (payment)",
     "previous bill paid",
     "",
     "-57485",
     "0",
     "0"
    ]
   ]
  }
 },
 "CMF_BALANCE": {
  "Table": {
   "name": "CMF_BALANCE",
   "src": "Customer DB, account balance per bill",
   "cols": [
    "account_no",
    "bill_ref_no",
    "new_charges",
    "total_adj",
    "total_paid",
    "balance_due",
    "dispute_amt"
   ],
   "rows": [
    [
     "3000245",
     "226001245",
     "34385",
     "0",
     "57485",
     "34385",
     "0"
    ],
    [
     "3000247",
     "226001247",
     "241250",
     "-5000",
     "239800",
     "236250",
     "0"
    ],
    [
     "3000248",
     "226001290",
     "110420",
     "0",
     "0",
     "167905",
     "53000"
    ]
   ]
  }
 },
 "ARM_COLLECTABLE · ARM_HISTORY": {
  "Table": {
   "name": "ARM_COLLECTABLE · ARM_HISTORY",
   "src": "Collections tables: overdue accounts, scenario and actions taken",
   "cols": [
    "account_no",
    "scenario",
    "entered",
    "overdue amount",
    "last action",
    "action date",
    "status"
   ],
   "rows": [
    [
     "3000248",
     "Consumer postpaid 30/60/90",
     "2026-11-05",
     "167905",
     "SMS reminder → outbound call",
     "2026-11-12",
     "in collections"
    ],
    [
     "3000251",
     "SME standard",
     "2026-10-28",
     "412000",
     "Soft barring",
     "2026-11-11",
     "promise to pay"
    ]
   ]
  }
 },
 "JNL_DETAIL → G/L feed": {
  "Table": {
   "name": "JNL_DETAIL",
   "src": "Customer DB, revenue mapped to accounting codes, then written to the journal feed file for the G/L",
   "cols": [
    "jnl_ref_no",
    "account_no",
    "bill_ref_no",
    "element_id",
    "jnl_code_id",
    "reported_amount",
    "currency_code",
    "jnl_feed_status"
   ],
   "rows": [
    [
     "J2611-0004410",
     "3000245",
     "226001245",
     "1299",
     "4100-MOBILE-RC",
     "29900",
     "682",
     "sent"
    ],
    [
     "J2611-0004411",
     "3000245",
     "226001245",
     "102",
     "4210-INTL-VOICE",
     "1680",
     "682",
     "sent"
    ],
    [
     "J2611-0004412",
     "3000245",
     "226001245",
     "—",
     "2300-VAT-OUTPUT",
     "4737",
     "682",
     "sent"
    ]
   ]
  }
 }
});

(function(){
 const css = `
 .klayer{display:inline-block;font:600 10.5px var(--font-mono);letter-spacing:.06em;padding:1px 6px;border-radius:4px;margin-bottom:4px;border:1px solid currentColor}
 .klayer.BSS{color:var(--bss)} .klayer.NSS{color:var(--nss)} .klayer.OSS{color:var(--oss)} .klayer.EXT{color:var(--muted)}
 td.kmod{width:180px;font-family:var(--font-mono);font-size:12px;color:var(--accent)}
 td.kland{width:240px;font-family:var(--font-mono);font-size:12px}
 td.kfrom{width:190px}
 .kflow{display:grid;gap:6px;margin:0 0 18px}
 .kflow .kr{display:grid;grid-template-columns:52px minmax(150px,220px) 1fr;gap:10px;align-items:center;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
 .kflow .ks{display:flex;flex-wrap:wrap;gap:4px 6px;align-items:center;font:500 12px var(--font-mono)}
 .kflow .km{padding:2px 7px;border-radius:4px;background:var(--accent-soft);color:var(--fg)}
 .kflow .ka{color:var(--muted)}
 .kflow .kt{padding:2px 7px;border-radius:4px;background:var(--soft);font-weight:600}
 .kflow .kfrom2{font-size:13px;color:var(--muted)}
 h3.kh{font-family:var(--font-display);font-stretch:85%;font-size:18px;margin:22px 0 6px}
 @media (max-width:900px){.kflow .kr{grid-template-columns:1fr}}`;
 const st=document.createElement("style"); st.textContent=css; document.head.appendChild(st);
})();

const KENAN_TROWS = KENAN_TABLES.map(t => ({sys:t[0], del:["Table"]}));

function kenanVisible(r){
  if (state.deliv.size && !r.del.some(d => state.deliv.has(d))) return false;
  if (!state.q) return true;
  return [r.sys,r.layer,r.from,r.data,r.fmt,r.del.join(" "),r.dn||"",r.intake,r.lands,r.api,r.sid].join(" ").toLowerCase().includes(state.q.toLowerCase());
}
function kenanHTML(){
  const rows = KENAN_FEEDS.filter(kenanVisible);
  const q = state.q.toLowerCase();
  const trows = KENAN_TABLES.filter(t => !q || t.join(" ").toLowerCase().includes(q));
  const sbtn = sys => `<br><button type="button" class="sbtn" data-toggle="${encodeURIComponent(sys)}" aria-expanded="${state.open.has(sys)}"><span class="car">›</span>Samples</button>`;
  const flow = `<div class="kflow">${KENAN_FLOW.map(([l,src,mods,out])=>`<div class="kr"><span>${l==="—"?"":`<span class="klayer ${l}">${l}</span>`}</span><span class="kfrom2">${esc(src)}</span>
     <span class="ks">${mods.map(m=>`<span class="km">${esc(m)}</span>`).join('<span class="ka">→</span>')}<span class="ka">→</span><span class="kt">${esc(out)}</span></span></div>`).join("")}</div>`;
  let html = `<section id="kenan"><div class="shead"><h2><span class="num">6</span>Kenan BP 12.0</h2><span class="count">${rows.length} of ${KENAN_FEEDS.length} feeds · ${trows.length} of ${KENAN_TABLES.length} tables</span></div>
   <p class="sub">Where Kenan's billing data comes from, the format and delivery of each feed, the Kenan module that takes it in, and the tables it ends up in. Field names and layouts are from the Kenan BP 12.0 manuals; sample values are invented.</p>
   ${flow}
   <h3 class="kh">Inbound feeds</h3>
   <div class="tblwrap"><table style="min-width:1500px"><thead><tr><th>Feed</th><th>Comes from</th><th>Key data</th><th>Format</th><th>Delivery</th><th>Kenan intake</th><th>Lands in</th><th>TMF API · SID</th></tr></thead><tbody>`;
  html += rows.length ? rows.map(r=>`<tr><td class="sys">${hi(r.sys)}${sbtn(r.sys)}</td>
     <td class="kfrom"><span class="klayer ${r.layer}">${r.layer==="EXT"?"EXTERNAL":r.layer}</span><br>${hi(r.from)}</td>
     <td class="data">${hi(r.data)}</td><td class="fmt">${hi(r.fmt)}</td>
     <td class="del"><div class="dchips">${r.del.map(d=>`<span class="dc ${d}">${d}</span>`).join("")}</div>${r.dn?`<div class="dnote">${hi(r.dn)}</div>`:""}</td>
     <td class="kmod">${hi(r.intake)}</td><td class="kland">${hi(r.lands)}</td>
     <td class="api">${hi(r.api)}<div class="sid" style="font-family:var(--font-body);color:var(--fg);font-size:13px;margin-top:4px">${hi(r.sid)}</div></td></tr>`
     + (state.open.has(r.sys) ? `<tr class="detail"><td colspan="8">${sampleHTML(r)}</td></tr>` : "")).join("")
     : `<tr><td colspan="8" class="empty">No feeds match these filters.</td></tr>`;
  html += `</tbody></table></div>
   <h3 class="kh">Final Kenan tables</h3>
   <p class="sub">What the modules build from those feeds, from the customer record through usage and billing to payments, collections and the ledger.</p>
   <div class="tblwrap"><table style="min-width:1300px"><thead><tr><th>Table</th><th>Database</th><th>Built by</th><th>Built from</th><th>One row per</th><th>Key columns</th><th>Used for</th></tr></thead><tbody>`;
  html += trows.length ? trows.map(t=>{ const has = KENAN_TABLE_SAMPLES[t[0]];
     return `<tr><td class="sys" style="font-family:var(--font-mono);font-size:12.5px">${hi(t[0])}${has?sbtn(t[0]):""}</td><td>${hi(t[1])}</td><td class="kmod">${hi(t[2])}</td><td>${hi(t[3])}</td><td>${hi(t[4])}</td><td class="kland">${hi(t[5])}</td><td>${hi(t[6])}</td></tr>`
     + (has && state.open.has(t[0]) ? `<tr class="detail"><td colspan="7">${sampleHTML({sys:t[0],del:["Table"]})}</td></tr>` : ""); }).join("")
     : `<tr><td colspan="7" class="empty">No tables match this search.</td></tr>`;
  html += `</tbody></table></div>
   <h3 class="kh">Notes</h3><div class="notes">${KENAN_NOTES.map(n=>`<div><b>${esc(n[0])}</b><p>${esc(n[1])}</p></div>`).join("")}</div></section>`;
  return { count: rows.length, html };
}
