"""
generator.py - Synthetic SAF-T-like XML data generator.

Generates realistic fake SAF-T XML files for multiple companies, injecting
normal, risky, and fraudulent behavioral patterns.

Each generated file is validated against the project XSD schema located at:
  schema/Ro_SAFT_Schema_v248_20231121.xsd

That file is a project-local schema derived from the Romanian ANAF SAF-T v2.48
specification.  Replace it with the official ANAF XSD once accessible:
  https://static.anaf.ro/static/10/Anaf/Informatii_R/Ro_SAFT_Schema_v248_20231121.xsd
"""

import random
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import date, timedelta

try:
    from lxml import etree as lxml_etree  # type: ignore
    _LXML_AVAILABLE = True
except ImportError:
    _LXML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RANDOM_SEED = 42
NUM_COMPANIES = 30
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw_xml")
SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "schema", "Ro_SAFT_Schema_v248_20231121.xsd"
)

COMPANY_SUFFIXES = ["SRL", "SA", "SNC", "RA", "GRUP", "INDUSTRIES", "TRADING"]
FIRST_NAMES = [
    "ALFA", "BETA", "GAMMA", "DELTA", "EPSILON", "SIGMA", "OMEGA",
    "NOVA", "APEX", "PRIMA", "INTER", "PRO", "ECO", "SMART", "FAST",
    "BLUE", "GREEN", "RED", "GOLDEN", "SILVER",
]
INDUSTRIES = [
    "CONSTRUCT", "RETAIL", "AGRO", "TECH", "TRANSPORT", "IMPORT-EXPORT",
    "SERVICES", "PHARMA", "ENERGY", "MEDIA",
]


def _random_date(start: date, end: date) -> date:
    """Return a random date between start and end (inclusive)."""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _prettify(elem: ET.Element) -> str:
    """Return a pretty-printed XML string for the Element."""
    raw = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(raw)
    return reparsed.toprettyxml(indent="  ")


def _make_tax_id(idx: int) -> str:
    """Generate a deterministic fake tax ID."""
    return f"RO{100000 + idx:08d}"


def _generate_partners(n: int, exclude_ids: set) -> list:
    """
    Generate n external partner stubs (customers / suppliers).
    Partners are shared across companies to enable network effects.
    """
    partners = []
    for i in range(n):
        pid = f"PART{1000 + i:04d}"
        if pid in exclude_ids:
            continue
        name = (
            random.choice(FIRST_NAMES)
            + " "
            + random.choice(INDUSTRIES)
            + " "
            + random.choice(COMPANY_SUFFIXES)
        )
        partners.append({"id": pid, "name": name, "tax_id": _make_tax_id(9000 + i)})
    return partners


def _generate_transactions(
    company_id: str,
    partner_ids: list,
    num_months: int,
    start_year: int = 2023,
    pattern: str = "normal",
) -> list:
    """
    Generate a list of transaction dicts for a company.

    Patterns:
      normal  - stable revenue, multiple partners
      risky   - high partner concentration + occasional spikes
      fraud   - directed at a specific set of ring partners
    """
    transactions = []
    tx_counter = 0
    start_date = date(start_year, 1, 1)

    for month_offset in range(num_months):
        month_date = date(start_year, 1, 1) + timedelta(days=30 * month_offset)
        year = month_date.year
        month = month_date.month
        month_start = date(year, month, 1)
        # last day of month (approx)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        if pattern == "normal":
            base_sales = random.randint(5, 15)
            base_purchases = random.randint(3, 10)
            sale_amount_range = (5_000, 50_000)
            purchase_amount_range = (2_000, 30_000)
        elif pattern == "risky":
            base_sales = random.randint(2, 20)
            base_purchases = random.randint(2, 8)
            # Occasional spike month
            spike = random.random() < 0.25
            sale_amount_range = (50_000, 500_000) if spike else (5_000, 40_000)
            purchase_amount_range = (3_000, 25_000)
        else:  # fraud
            base_sales = random.randint(3, 12)
            base_purchases = random.randint(3, 12)
            sale_amount_range = (20_000, 200_000)
            purchase_amount_range = (20_000, 200_000)

        # Sales transactions
        for _ in range(base_sales):
            if pattern == "risky" and random.random() < 0.6:
                # Concentrate on first partner
                partner = partner_ids[0]
            else:
                partner = random.choice(partner_ids)

            tx_date = _random_date(month_start, month_end)
            amount = round(random.uniform(*sale_amount_range), 2)
            tx_counter += 1
            transactions.append(
                {
                    "transaction_id": f"{company_id}_TX{tx_counter:05d}",
                    "company_id": company_id,
                    "partner_id": partner,
                    "amount": amount,
                    "date": tx_date.isoformat(),
                    "type": "sale",
                }
            )

        # Purchase transactions
        for _ in range(base_purchases):
            partner = random.choice(partner_ids)
            tx_date = _random_date(month_start, month_end)
            amount = round(random.uniform(*purchase_amount_range), 2)
            tx_counter += 1
            transactions.append(
                {
                    "transaction_id": f"{company_id}_TX{tx_counter:05d}",
                    "company_id": company_id,
                    "partner_id": partner,
                    "amount": amount,
                    "date": tx_date.isoformat(),
                    "type": "purchase",
                }
            )

    return transactions


def _build_xml(company: dict, partners: list, transactions: list) -> str:
    """Build a SAF-T-like XML string for one company."""
    root = ET.Element("AuditFile")
    root.set("xmlns", "urn:StandardAuditFile-Taxation:RO_2.48")

    # --- Header ---
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "AuditFileVersion").text = "2.48"
    ET.SubElement(header, "AuditFileCountry").text = "RO"
    ET.SubElement(header, "AuditFileDateCreated").text = date.today().isoformat()
    ET.SubElement(header, "SoftwareCompanyName").text = "SAF-T PoC Generator"
    ET.SubElement(header, "SoftwareID").text = "saft-poc-v1"
    ET.SubElement(header, "SoftwareVersion").text = "1.0"

    company_elem = ET.SubElement(header, "Company")
    ET.SubElement(company_elem, "RegistrationNumber").text = company["tax_id"]
    name_elem = ET.SubElement(company_elem, "Name")
    name_elem.text = company["name"]
    ET.SubElement(company_elem, "CompanyID").text = company["id"]

    # --- MasterFiles > Customers / Suppliers ---
    master = ET.SubElement(root, "MasterFiles")
    partner_map = {p["id"]: p for p in partners}

    seen_customers = set()
    seen_suppliers = set()
    for tx in transactions:
        if tx["type"] == "sale" and tx["partner_id"] not in seen_customers:
            seen_customers.add(tx["partner_id"])
            p = partner_map.get(tx["partner_id"], {})
            cust = ET.SubElement(master, "Customer")
            ET.SubElement(cust, "CustomerID").text = tx["partner_id"]
            ET.SubElement(cust, "Name").text = p.get("name", tx["partner_id"])
            ET.SubElement(cust, "TaxID").text = p.get("tax_id", "")

        elif tx["type"] == "purchase" and tx["partner_id"] not in seen_suppliers:
            seen_suppliers.add(tx["partner_id"])
            p = partner_map.get(tx["partner_id"], {})
            sup = ET.SubElement(master, "Supplier")
            ET.SubElement(sup, "SupplierID").text = tx["partner_id"]
            ET.SubElement(sup, "Name").text = p.get("name", tx["partner_id"])
            ET.SubElement(sup, "TaxID").text = p.get("tax_id", "")

    # --- GeneralLedgerEntries (Transactions) ---
    gl = ET.SubElement(root, "GeneralLedgerEntries")
    for tx in transactions:
        entry = ET.SubElement(gl, "Journal")
        ET.SubElement(entry, "TransactionID").text = tx["transaction_id"]
        ET.SubElement(entry, "TransactionDate").text = tx["date"]
        ET.SubElement(entry, "TransactionType").text = tx["type"]
        ET.SubElement(entry, "Amount").text = str(tx["amount"])
        ET.SubElement(entry, "PartnerID").text = tx["partner_id"]
        ET.SubElement(entry, "CompanyID").text = tx["company_id"]

    return _prettify(root)


def _validate_xml(xml_path: str, schema_path: str = SCHEMA_PATH) -> bool:
    """
    Validate an XML file against the SAF-T XSD schema using lxml.

    Returns True if valid.  Prints a warning and returns False if the file
    fails validation or if lxml is unavailable.
    """
    if not _LXML_AVAILABLE:
        print(
            "[generator] WARNING: lxml not installed — XSD validation skipped. "
            "Run `pip install lxml` to enable schema validation."
        )
        return True

    if not os.path.isfile(schema_path):
        print(
            f"[generator] WARNING: XSD schema not found at {schema_path} "
            "— validation skipped."
        )
        return True

    try:
        with open(schema_path, "rb") as fh:
            schema = lxml_etree.XMLSchema(lxml_etree.parse(fh))
        with open(xml_path, "rb") as fh:
            doc = lxml_etree.parse(fh)
        if schema.validate(doc):
            return True
        errors = [str(e) for e in schema.error_log]
        print(
            f"[generator] VALIDATION FAILED: {os.path.basename(xml_path)}\n"
            + "\n".join(f"  {e}" for e in errors)
        )
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"[generator] WARNING: Unexpected error during XSD validation of "
              f"{os.path.basename(xml_path)}: {exc}")
        return False


def generate(output_dir: str = DATA_DIR, seed: int = RANDOM_SEED) -> list:
    """
    Generate synthetic SAF-T XML files for multiple companies.

    Returns a list of company metadata dicts.
    """
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    # --- Build company list ---
    companies = []
    for i in range(NUM_COMPANIES):
        cid = f"COMP{i + 1:04d}"
        name = (
            random.choice(FIRST_NAMES)
            + " "
            + random.choice(INDUSTRIES)
            + " "
            + random.choice(COMPANY_SUFFIXES)
        )
        pattern = "normal"
        if i in range(20, 26):
            pattern = "risky"
        elif i in range(26, 30):
            pattern = "fraud"
        companies.append(
            {
                "id": cid,
                "name": name,
                "tax_id": _make_tax_id(i),
                "pattern": pattern,
                "num_months": random.randint(3, 12),
            }
        )

    company_ids = {c["id"] for c in companies}

    # --- Build global partner pool ---
    all_partners = _generate_partners(80, exclude_ids=company_ids)

    # --- Build fraud ring: companies 26-29 form a circular chain ---
    # COMP0027 -> COMP0028 -> COMP0029 -> COMP0030 -> COMP0027
    fraud_ring_ids = [companies[26]["id"], companies[27]["id"],
                      companies[28]["id"], companies[29]["id"]]

    # --- Generate XML per company ---
    validation_failures: list[str] = []
    for company in companies:
        cid = company["id"]
        pattern = company["pattern"]
        num_months = company["num_months"]

        if pattern == "normal":
            # Use a diverse mix of external partners
            partner_subset = random.sample(all_partners, k=random.randint(8, 20))
        elif pattern == "risky":
            # Use few partners to simulate concentration
            partner_subset = random.sample(all_partners, k=random.randint(2, 5))
        else:
            # Fraud companies trade mainly with each other (ring) plus a few external
            ring_partners_as_objects = []
            for rid in fraud_ring_ids:
                if rid != cid:
                    ring_comp = next(c for c in companies if c["id"] == rid)
                    ring_partners_as_objects.append(
                        {"id": rid, "name": ring_comp["name"],
                         "tax_id": ring_comp["tax_id"]}
                    )
            external = random.sample(all_partners, k=random.randint(1, 3))
            partner_subset = ring_partners_as_objects + external

        partner_ids_for_company = [p["id"] for p in partner_subset]

        transactions = _generate_transactions(
            company_id=cid,
            partner_ids=partner_ids_for_company,
            num_months=num_months,
            pattern=pattern,
        )

        xml_str = _build_xml(company, partner_subset, transactions)
        out_path = os.path.join(output_dir, f"{cid}.xml")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(xml_str)
        if not _validate_xml(out_path):
            validation_failures.append(cid)

    if validation_failures:
        print(
            f"[generator] WARNING: {len(validation_failures)} file(s) failed "
            f"XSD validation: {validation_failures}"
        )
    else:
        print(
            f"[generator] All {len(companies)} files passed XSD schema validation."
        )
    print(f"[generator] Generated {len(companies)} XML files in {output_dir}")
    return companies


if __name__ == "__main__":
    generate()
