"""
Do tim thong tin (stage, trang thai...) cua mot serial qua ATS web service (SFCS).

CHI GOI CAC HAM CHI-DOC (get*/Get*/ATS_Query*), chon tay theo ten ham. Khong goi ham Set/Insert/Update/
Delete/Save/Hold/Start/Cancel... Ten ham khong luon noi dung viec ham lam: neu muon them ham vao PROBES,
hoi nguoi quan tri SFC truoc.

Cach dung:
    pip install zeep
    python sfcs_probe.py NALNO50H00DGH01        (hoac chay khong tham so, chuong trinh se hoi serial)
    python sfcs_probe.py NALNO50H00DGH01 --cpn @H_SID_1212 --qualifier NALN
Ket qua in ra man hinh va luu vao sfcs_probe_<serial>.json
Doi chieu gia tri stage trong bao cao SN Query voi ket qua de biet ham/truong nao chua stage.
"""
import argparse
import json
import sys

from lxml import etree
from requests import Session
from zeep import Client
from zeep.helpers import serialize_object
from zeep.transports import Transport

WSDL = "http://v2haproxy_vip.wneweb.com.tw:100/sfcs_webservice/ats.asmx?WSDL"

# (ten ham, ten tham so chua serial, cac tham so khac). Ten/kieu chu hoa-thuong lay dung theo danh sach ham.
# Cac gia tri "@CPN@" va "@QUALIFIER@" duoc thay bang tham so dong lenh.
PROBES = [
    ("ATS_Query_All_CSN",      "CSN",         {"CPN": "@CPN@", "ErrMsg": ""}),
    ("ATS_Query_CSN",          "CSN",         {"CPN": "@CPN@", "ErrMsg": ""}),
    ("getFLEXFIELD_ByCSN",     "CSN",         {"qualifier": "@QUALIFIER@", "errMsg": ""}),
    ("getFLEXFIELD_BySSN",     "CSN",         {"qualifier": "@QUALIFIER@", "errMsg": ""}),
    ("getSPC_FLEXFIELD",       "CSN",         {"errMsg": ""}),
    ("getAllCsnByCsn",         "CSN",         {"errMsg": ""}),
    ("getAllCsn",              "vs_ssn",      {"errMsg": ""}),
    ("getSN_ByCSN",            "CSN",         {"CPN": "@CPN@", "errMsg": ""}),
    ("getProdSSN_ByCSN",       "CSN",         {"errMsg": ""}),
    ("getModelNamebyCSN",      "CSN",         {"errMsg": ""}),
    ("getCreatedTime_byCsn",   "strCSN",      {"errMsg": ""}),
    ("getMODownLoadTimeByCSN", "CSN",         {"errMsg": ""}),
    ("getMOLineByMACSN",       "CSN",         {"errMsg": ""}),
    ("getPNGNDSbyCSN",         "CSN",         {"errMsg": ""}),
    ("get_45PN_By_CSN",        "CSN",         {"errMsg": ""}),
    ("GetPsn",                 "Vs_CheckSn",  {}),
    ("GetPN_BySN",             "Vs_CheckSsn", {"ErrMsg": ""}),
    ("GetWO_BySN",             "Vs_CheckSsn", {"ErrMsg": ""}),
    ("Get_SsnLastReason",      "PSN",         {}),
    ("getEquipPass",           "psn",         {"errMsg": ""}),
    ("get_ProdData",           "vs_ssn",      {"errMsg": ""}),
    ("getSN_ForATS",           "SSN",         {"errMsg": ""}),
]


def rows_of(node):
    """Doi mot DataSet (lxml) thanh danh sach dong {cot: gia tri}."""
    nodes = node if isinstance(node, list) else [node]
    rows = []
    for n in nodes:
        if not isinstance(n, etree._Element):
            continue
        for e in n.iter():
            kids = [k for k in e if isinstance(k.tag, str)]
            if kids and all(len([x for x in k if isinstance(x.tag, str)]) == 0 for k in kids):
                rows.append({etree.QName(k).localname: (k.text or "") for k in kids})
    return rows


def plain(v):
    """Chuyen ket qua zeep (dict/list/lxml) thanh du lieu in/luu duoc."""
    if isinstance(v, etree._Element):
        return rows_of(v) or etree.tostring(v, encoding="unicode")
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items() if k != "schema"}
    if isinstance(v, (list, tuple)):
        if v and all(isinstance(x, etree._Element) for x in v):
            return rows_of(list(v)) or [etree.tostring(x, encoding="unicode") for x in v]
        return [plain(x) for x in v]
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("serial", nargs="?", help="serial can tra (vi du CSN); bo trong thi chuong trinh se hoi")
    ap.add_argument("--cpn", default="@H_SID_1212", help="tham so CPN (mac dinh nhu trong tin nhan mau)")
    ap.add_argument("--qualifier", default="NALN", help="qualifier cho getFLEXFIELD_*")
    ap.add_argument("--wsdl", default=WSDL)
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()
    if not args.serial:                                   # chay tu PyCharm/IDE khong co tham so
        args.serial = input("Nhap serial can tra: ").strip()
        if not args.serial:
            ap.error("chua co serial")

    client = Client(args.wsdl, transport=Transport(session=Session(), timeout=args.timeout))
    subst = {"@CPN@": args.cpn, "@QUALIFIER@": args.qualifier}

    candidates = [args.serial]               # serial goc; them gia tri ATS_Query_All_CSN tra ve neu khac
    results = {}
    i = 0
    while i < len(candidates):
        serial = candidates[i]
        i += 1
        print("=" * 70)
        print("SERIAL:", serial)
        for name, serial_param, extra in PROBES:
            kwargs = {k: subst.get(v, v) for k, v in extra.items()}
            kwargs[serial_param] = serial
            key = "%s(%s)" % (name, serial)
            try:
                res = plain(serialize_object(getattr(client.service, name)(**kwargs)))
            except Exception as ex:                       # ham khong ton tai, loi mang, loi SOAP...
                res = "!! %s: %s" % (type(ex).__name__, ex)
            results[key] = res
            text = json.dumps(res, ensure_ascii=False, default=str)
            print("-- %s -> %s" % (name, text if len(text) <= 600 else text[:600] + " ...(cat bot)"))
            # ATS_Query_All_CSN tra ve chuoi (serial khac): thu them voi serial do
            if name == "ATS_Query_All_CSN" and serial == args.serial:
                val = res.get("ATS_Query_All_CSNResult") if isinstance(res, dict) else res
                if isinstance(val, str) and val.strip() and val.strip() not in candidates:
                    candidates.append(val.strip())
                    print("   (ham tra ve '%s': se thu them cac ham voi gia tri nay)" % val.strip())

    out = "sfcs_probe_%s.json" % args.serial
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1, default=str)
    print("\nDa luu:", out)


if __name__ == "__main__":
    sys.exit(main())