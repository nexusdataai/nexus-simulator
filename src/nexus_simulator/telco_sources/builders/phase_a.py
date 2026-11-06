"""Phase A builders — trace-correlated systems from Telco-Data samples."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from nexus_simulator.plugins.telco_seed_pools import TelcoPools
from nexus_simulator.telco_sources.identity import (
    atlas_cell_name,
    atlas_customer_id,
    atlas_enb,
    atlas_imsi,
    atlas_msisdn,
    trace_customer_internal,
)
from nexus_simulator.telco_sources.models import Artifact, TelcoProductOffer, TelcoSourceProfile


def _product_rows(profile: TelcoSourceProfile) -> list[list]:
    rows = []
    for p in profile.products or []:
        rows.append(
            [
                p.offer_id,
                p.name,
                p.offer_type,
                f"{p.price_sar:.2f}",
                p.recurrence,
                str(p.data_gb) if p.data_gb is not None else "—",
                "unlimited" if p.offer_type == "plan" else "—",
                "Launched",
            ]
        )
    if not rows:
        rows.append(["PO-POST-299", "Postpaid 299", "plan", "299.00", "monthly", "25", "unlimited on-net", "Launched"])
    return rows


def build_crm(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    cols = [
        "CUSTOMER_ID",
        "FULL_NAME",
        "SEGMENT",
        "ACCOUNT_TYPE",
        "REGION",
        "ACTIVATION_DATE",
        "STATUS",
        "KYC_STATUS",
    ]
    rows = []
    for cid in pools.customer_ids[: min(20, len(pools.customer_ids))]:
        plan_name, _, _, acct, _ = pools.customer_plan[cid]
        rows.append(
            [
                atlas_customer_id(pools, cid),
                f"Subscriber {cid}",
                pools.customer_segment[cid],
                acct,
                pools.customer_region[cid],
                pools.date_str(800, 30),
                "ACTIVE",
                "VERIFIED",
            ]
        )
    trace = trace_customer_internal(pools)
    trace_c = atlas_customer_id(pools, trace)
    api_body = {
        "id": trace_c,
        "@type": "Customer",
        "name": "Faisal Al-Harbi",
        "status": "Approved",
        "engagedParty": {"id": "P-55120", "@referredType": "Individual"},
        "account": [{"id": "BA-7781203", "name": "Postpaid billing account", "@referredType": "BillingAccount"}],
        "characteristic": [
            {"name": "segment", "value": pools.customer_segment[trace]},
            {"name": "tenureMonths", "value": pools.customer_tenure[trace]},
            {"name": "region", "value": pools.customer_region[trace]},
        ],
        "validFor": {"startDateTime": "2024-08-14T09:12:00+03:00"},
    }
    csv_lines = ["Id,Name,Segment__c,Account_Type__c,Region__c,Activation_Date__c,Status__c,KYC_Status__c"]
    for r in rows[:5]:
        csv_lines.append(f"{r[0]},Subscriber,{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]}")
    return [
        Artifact(
            "CRM / customer master",
            "BSS",
            "Table",
            "CRM.CUSTOMER_PROFILE",
            table_name="CRM.CUSTOMER_PROFILE",
            columns=cols,
            rows=rows,
        ),
        Artifact(
            "CRM / customer master",
            "BSS",
            "API",
            f"customer_{trace_c}",
            api_method="GET",
            api_path=f"/tmf-api/customerManagement/v5/customer/{trace_c}",
            api_body=api_body,
        ),
        Artifact(
            "CRM / customer master",
            "BSS",
            "File",
            "customer_extract.csv",
            mime="text/csv",
            content="\n".join(csv_lines) + "\n",
            file_path="incoming/bss/crm/customer_extract.csv",
        ),
    ]


def build_product_catalog(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    cols = ["OFFER_ID", "OFFER_NAME", "OFFER_TYPE", "PRICE_SAR", "RECURRENCE", "DATA_GB", "VOICE_MIN", "LIFECYCLE"]
    rows = _product_rows(profile)
    offer = profile.products[1].offer_id if len(profile.products) > 1 else "PO-POST-499"
    return [
        Artifact(
            "Product catalog",
            "BSS",
            "Table",
            "PC.PRODUCT_OFFERING",
            table_name="PC.PRODUCT_OFFERING",
            columns=cols,
            rows=rows,
        ),
        Artifact(
            "Product catalog",
            "BSS",
            "API",
            f"offering_{offer}",
            api_method="GET",
            api_path=f"/tmf-api/productCatalogManagement/v5/productOffering/{offer}",
            api_body={
                "id": offer,
                "@type": "ProductOffering",
                "name": profile.products[1].name if len(profile.products) > 1 else "Postpaid 499",
                "lifecycleStatus": "Launched",
            },
        ),
    ]


def build_subscriptions(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    cols = ["PRODUCT_ID", "CUSTOMER_ID", "MSISDN", "OFFER", "STATUS", "START_DATE", "CONTRACT_END", "INSTALMENTS_LEFT"]
    rows = []
    for i, cid in enumerate(pools.customer_ids[:10]):
        plan_name, _, _, _, _ = pools.customer_plan[cid]
        rows.append(
            [
                f"PRD-900124{5 + i}",
                atlas_customer_id(pools, cid),
                atlas_msisdn(pools, cid),
                plan_name,
                "active",
                pools.date_str(400, 30),
                pools.date_str(30, 0),
                str(pools.rng().randint(0, 5)),
            ]
        )
    trace = trace_customer_internal(pools)
    trace_c = atlas_customer_id(pools, trace)
    return [
        Artifact(
            "Subscriptions / installed base",
            "BSS",
            "Table",
            "INV.SUBSCRIBER_PRODUCT",
            table_name="INV.SUBSCRIBER_PRODUCT",
            columns=cols,
            rows=rows,
        ),
        Artifact(
            "Subscriptions / installed base",
            "BSS",
            "API",
            "PRD-9001245",
            api_method="GET",
            api_path="/tmf-api/productInventory/v5/product/PRD-9001245",
            api_body={
                "id": "PRD-9001245",
                "@type": "Product",
                "name": "Postpaid 299",
                "status": "active",
                "productCharacteristic": [
                    {"name": "MSISDN", "value": atlas_msisdn(pools, trace)},
                    {"name": "IMSI", "value": atlas_imsi(pools, trace)},
                ],
                "relatedParty": [{"id": trace_c, "role": "Customer"}],
            },
        ),
    ]


def build_ocs(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    trace = trace_customer_internal(pools)
    msisdn = atlas_msisdn(pools, trace)
    content = (
        "EVENT_ID|MSISDN|SERVICE|RATING_GROUP|START_TIME|DURATION_S|VOLUME_KB|CHARGE_SAR|BALANCE_AFTER|BUCKET\n"
        f"E8812340001|{msisdn}|DATA|100|20261105140212|900|184320|0.00|3.21GB|PO-POST-299 data\n"
    )
    return [
        Artifact(
            "Online charging (OCS / CCS / CHF)",
            "BSS",
            "File",
            "CBS_EDR_RATED.csv",
            mime="text/csv",
            content=content,
            file_path="incoming/bss/ocs/CBS_EDR_RATED.csv",
        ),
        Artifact(
            "Online charging (OCS / CCS / CHF)",
            "BSS",
            "Stream",
            "ocs.balance.notifications",
            stream_topic="ocs.balance.notifications",
            stream_events=[
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "key": msisdn,
                    "v": {"event": "FUP_LIMIT_HIT", "bucket": "data", "action": "throttle_1mbps"},
                }
            ],
        ),
    ]


def build_mediation(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    trace = trace_customer_internal(pools)
    imsi = atlas_imsi(pools, trace)
    msisdn = atlas_msisdn(pools, trace)
    home = pools.home_cell_by_customer[trace]
    cell = atlas_cell_name(pools, home, trace=True)
    enb = atlas_enb(cell)
    content = (
        "record_id,source_node,record_type,imsi,msisdn,start_time,duration_s,uplink_bytes,downlink_bytes,rat,ecgi,apn\n"
        f"MD-00451-001,PGW01,PGW-CDR,{imsi},{msisdn},2026-11-05T14:00:12+03:00,900,8123456,180112334,EUTRAN,001-01-{enb[3:]}-1,internet.nimbus\n"
    )
    return [
        Artifact(
            "Mediation",
            "BSS",
            "File",
            "MED_USAGE_NORMALISED.csv",
            mime="text/csv",
            content=content,
            file_path="incoming/mediation/MED_USAGE_NORMALISED.csv",
        ),
    ]


def build_care(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    trace_c = atlas_customer_id(pools, trace_customer_internal(pools))
    return [
        Artifact(
            "Customer care / complaints",
            "BSS",
            "Table",
            "CARE.TICKET",
            table_name="CARE.COMPLAINT",
            columns=["TICKET_ID", "CUSTOMER_ID", "REASON", "STATUS", "CONTACTS_30D"],
            rows=[["CS-240983", trace_c, "network_quality", "open", "3"]],
        ),
        Artifact(
            "Customer care / complaints",
            "BSS",
            "API",
            "CS-240983",
            api_method="GET",
            api_path="/tmf-api/troubleTicket/v5/troubleTicket/CS-240983",
            api_body={"id": "CS-240983", "@type": "TroubleTicket", "status": "inProgress", "relatedParty": [{"id": trace_c}]},
        ),
    ]


def build_enm_fm(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    cell = "RYD-0421-L18-1"
    return [
        Artifact(
            "Element manager: Fault (FM)",
            "OSS",
            "Stream",
            "oss.enm.fm.alarms",
            stream_topic="oss.enm.fm.alarms",
            stream_events=[
                {
                    "ts": "2026-11-05T13:42:07.000+03:00",
                    "key": "ALM-9930021",
                    "v": {
                        "notificationType": "notifyNewAlarm",
                        "objectInstance": f"MeContext=ENB104210,EUtranCellFDD={cell}",
                        "perceivedSeverity": "CRITICAL",
                    },
                }
            ],
        ),
        Artifact(
            "Element manager: Fault (FM)",
            "OSS",
            "API",
            "ALM-9930021",
            api_method="GET",
            api_path="/tmf-api/alarmManagement/v5/alarm/ALM-9930021",
            api_body={
                "id": "ALM-9930021",
                "@type": "Alarm",
                "perceivedSeverity": "critical",
                "alarmedObject": {"id": cell, "@referredType": "Resource"},
            },
        ),
    ]


def build_enm_pm(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<measCollecFile xmlns="http://www.3gpp.org/ftp/specs/archive/32_series/32.435#measCollec">
  <fileHeader fileFormatVersion="32.435 V10.0" vendorName="Ericsson">
    <fileSender localDn="SubNetwork=RYD,MeContext=ENB104210"/>
    <measCollec beginTime="2026-11-05T14:00:00+03:00"/>
  </fileHeader>
  <measData>
    <measValue measObjLdn="EUtranCellFDD=RYD-0421-L18-1">
      <r p="3">0</r><suspect>true</suspect>
    </measValue>
  </measData>
</measCollecFile>
"""
    return [
        Artifact(
            "Element manager: Performance (PM)",
            "OSS",
            "File",
            "A20261105_statsfile.xml",
            mime="application/xml",
            content=xml,
            file_path="incoming/pm/A20261105_statsfile.xml",
        ),
    ]


def build_kpi_warehouse(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    return [
        Artifact(
            "PM / statistics warehouse",
            "OSS",
            "Table",
            "DC_E_ERBS_EUTRANCELLFDD_DAY",
            table_name="DC_E_ERBS_EUTRANCELLFDD_DAY",
            columns=["DATE_ID", "ERBS", "EUTRANCELLFDD", "AVAILABILITY_PCT", "RRC_SR_PCT", "ERAB_DROP_PCT", "DL_THP_MBPS", "PRB_UTIL_DL_PCT"],
            rows=[["2026-11-04", "ENB104210", "RYD-0421-L18-1", "71.4", "96.2", "2.81", "9.4", "91"]],
        ),
    ]


def build_remedy(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    return [
        Artifact(
            "Trouble tickets (network)",
            "OSS",
            "Table",
            "HPD:Help Desk",
            table_name="HPD_Help_Desk",
            columns=["INCIDENT_NUMBER", "SUMMARY", "PRIORITY", "STATUS", "CI", "REPORTED_DATE", "RESOLVED_DATE", "MTTR_H"],
            rows=[["INC000012345", "RYD-0421 site down, MW link", "High", "Resolved", "ENB104210", "2026-11-05 13:45", "2026-11-05 15:12", "1.5"]],
        ),
    ]


def build_inventory(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    cell = "RYD-0421-L18-1"
    return [
        Artifact(
            "Planning / cell inventory",
            "OSS",
            "Table",
            "INV.CELL",
            table_name="INV.CELL",
            columns=["CELL_ID", "SITE_ID", "TECHNOLOGY", "BAND", "AZIMUTH", "ELEC_TILT", "STATUS", "LAST_UPDATED"],
            rows=[[cell, "RYD-0421", "LTE", "1800", "30", "4", "in-service", "2026-10-27"]],
        ),
        Artifact(
            "Planning / cell inventory",
            "OSS",
            "API",
            cell,
            api_method="GET",
            api_path=f"/tmf-api/resourceInventoryManagement/v5/resource/{cell}",
            api_body={"id": cell, "@type": "LogicalResource", "resourceStatus": "available", "operationalState": "disable"},
        ),
    ]


def build_pgw(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    trace = trace_customer_internal(pools)
    imsi = atlas_imsi(pools, trace)
    msisdn = atlas_msisdn(pools, trace)
    cdr = f"""-- PGW-CDR decoded
pGWRecord {{
  servedIMSI {imsi}
  servedMSISDN {msisdn}
  userLocationInformation ECGI 001-01-104210-1
  duration 900
}}
"""
    return [
        Artifact(
            "Packet gateway (SGW / PGW / SMF / UPF)",
            "NSS",
            "File",
            "PGW01_decoded.txt",
            mime="text/plain",
            content=cdr,
            file_path="incoming/cdr/PGW01_decoded.txt",
        ),
    ]


def build_mme(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    imsi = atlas_imsi(pools, trace_customer_internal(pools))
    return [
        Artifact(
            "MME / AMF (mobility)",
            "NSS",
            "Stream",
            "mme.ebm.events",
            stream_topic="mme.ebm.events",
            stream_events=[
                {
                    "ts": "2026-11-05T13:42:15.210+03:00",
                    "key": imsi,
                    "v": {"event": "L_SERVICE_REQUEST", "result": "REJECT", "cause": "eNB_NOT_AVAILABLE"},
                }
            ],
        ),
    ]


def build_pcf(pools: TelcoPools, profile: TelcoSourceProfile) -> List[Artifact]:
    msisdn = atlas_msisdn(pools, trace_customer_internal(pools))
    return [
        Artifact(
            "PCRF / PCF (policy)",
            "NSS",
            "File",
            "PCF_POLICY_EVENTS.csv",
            mime="text/csv",
            content=f"event_time,msisdn,event,action\n2026-11-05T14:31:03+03:00,{msisdn},QUOTA_THRESHOLD,THROTTLE\n",
            file_path="incoming/nss/pcf/PCF_POLICY_EVENTS.csv",
        ),
    ]


PHASE_A_BUILDERS = {
    "CRM / customer master": build_crm,
    "Product catalog": build_product_catalog,
    "Subscriptions / installed base": build_subscriptions,
    "Online charging (OCS / CCS / CHF)": build_ocs,
    "Mediation": build_mediation,
    "Customer care / complaints": build_care,
    "Element manager: Fault (FM)": build_enm_fm,
    "Element manager: Performance (PM)": build_enm_pm,
    "PM / statistics warehouse": build_kpi_warehouse,
    "Trouble tickets (network)": build_remedy,
    "Planning / cell inventory": build_inventory,
    "Packet gateway (SGW / PGW / SMF / UPF)": build_pgw,
    "MME / AMF (mobility)": build_mme,
    "PCRF / PCF (policy)": build_pcf,
}
