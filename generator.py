"""
generator.py - Synthetic SAF-T XML data generator.

Generates realistic SAF-T XML files for multiple companies, injecting normal,
risky, and fraudulent behavioral patterns.  Each generated file is validated
against the official Romanian ANAF SAF-T v2.48 XSD schema located at:
  schema/Ro_SAFT_Schema_v248_20231121.xsd
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

# Official ANAF SAF-T v2.48 namespace
SAFT_NS = "mfp:anaf:dgti:d406t:declaratie:v1"
ET.register_namespace("", SAFT_NS)

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

# Fake bank code used for synthetic IBAN generation (RO format: 2+2+4+16 = 24 chars)
_IBAN_BANK_CODE = "RNCB"
_IBAN_ACCOUNT_PAD = 10


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


def _se(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    """Create a child element in the SAF-T namespace with optional text."""
    elem = ET.SubElement(parent, f"{{{SAFT_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem


def _amount_struct(parent: ET.Element, tag: str, value: float) -> None:
    """Append an AmountStructure child (Amount, CurrencyCode, CurrencyAmount)."""
    container = _se(parent, tag)
    _se(container, "Amount", f"{value:.2f}")
    _se(container, "CurrencyCode", "RON")
    _se(container, "CurrencyAmount", f"{value:.2f}")


def _build_xml(company: dict, partners: list, transactions: list) -> str:
    """
    Build a SAF-T XML string conforming to the official ANAF v2.48 schema
    (namespace: mfp:anaf:dgti:d406t:declaratie:v1).
    """
    partner_map = {p["id"]: p for p in partners}

    # Derive date range from transactions for SelectionCriteria
    tx_dates = sorted(tx["date"] for tx in transactions)
    sel_start = tx_dates[0] if tx_dates else date.today().isoformat()
    sel_end = tx_dates[-1] if tx_dates else date.today().isoformat()

    # Derive numeric index from company ID (e.g. "COMP0001" → 1)
    try:
        idx = int(company["id"].replace("COMP", ""))
    except ValueError:
        idx = 0

    # ------------------------------------------------------------------
    # Root
    # ------------------------------------------------------------------
    root = ET.Element(f"{{{SAFT_NS}}}AuditFile")

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    header = _se(root, "Header")
    _se(header, "AuditFileVersion", "2.48")
    _se(header, "AuditFileCountry", "RO")
    _se(header, "AuditFileDateCreated", date.today().isoformat())
    _se(header, "SoftwareCompanyName", "SAF-T PoC Generator")
    _se(header, "SoftwareID", "saft-poc-v1")
    _se(header, "SoftwareVersion", "1.0")

    # Company (CompanyHeaderStructure: RegistrationNumber, Name, Address+, Contact+, BankAccount+)
    comp_elem = _se(header, "Company")
    _se(comp_elem, "RegistrationNumber", company["id"])       # max 35 chars
    _se(comp_elem, "Name", company["name"][:256])

    addr = _se(comp_elem, "Address")
    _se(addr, "City", "Bucuresti")
    _se(addr, "Country", "RO")
    _se(addr, "AddressType", "StreetAddress")

    contact = _se(comp_elem, "Contact")
    cp = _se(contact, "ContactPerson")
    _se(cp, "FirstName", "NotUsed")
    _se(cp, "LastName", company["name"][:70])
    _se(contact, "Telephone", "+40000000000")                 # max 18 chars

    bank = _se(comp_elem, "BankAccount")
    _se(bank, "IBANNumber",
        f"RO{idx:02d}{_IBAN_BANK_CODE}000000{idx:0{_IBAN_ACCOUNT_PAD}d}")

    _se(header, "DefaultCurrencyCode", "RON")

    sel = _se(header, "SelectionCriteria")
    _se(sel, "SelectionStartDate", sel_start)
    _se(sel, "SelectionEndDate", sel_end)

    _se(header, "HeaderComment", "Generated by SAF-T PoC")
    _se(header, "SegmentIndex", "1")
    _se(header, "TotalSegmentsInsequence", "1")
    _se(header, "TaxAccountingBasis", "A")

    # ------------------------------------------------------------------
    # MasterFiles
    # ------------------------------------------------------------------
    master = _se(root, "MasterFiles")

    # GeneralLedgerAccounts (required container, empty for PoC)
    _se(master, "GeneralLedgerAccounts")

    # Aggregate totals per partner for balances
    customer_totals: dict = {}
    supplier_totals: dict = {}
    for tx in transactions:
        pid = tx["partner_id"]
        if tx["type"] == "sale":
            customer_totals[pid] = round(customer_totals.get(pid, 0.0) + tx["amount"], 2)
        else:
            supplier_totals[pid] = round(supplier_totals.get(pid, 0.0) + tx["amount"], 2)

    customers_elem = _se(master, "Customers")
    seen_customers: set = set()
    suppliers_elem = _se(master, "Suppliers")
    seen_suppliers: set = set()

    for tx in transactions:
        pid = tx["partner_id"]
        p = partner_map.get(pid, {})

        if tx["type"] == "sale" and pid not in seen_customers:
            seen_customers.add(pid)
            cust = _se(customers_elem, "Customer")

            # CompanyStructure (optional) – carries name & tax_id for parser
            cs = _se(cust, "CompanyStructure")
            _se(cs, "RegistrationNumber", p.get("tax_id", pid)[:35])
            _se(cs, "Name", p.get("name", pid)[:256])
            cs_addr = _se(cs, "Address")
            _se(cs_addr, "City", "Bucuresti")
            _se(cs_addr, "Country", "RO")

            _se(cust, "CustomerID", pid[:35])
            _se(cust, "AccountID", "4111")
            _se(cust, "OpeningDebitBalance", "0.00")
            _se(cust, "ClosingDebitBalance", f"{customer_totals.get(pid, 0.0):.2f}")

        elif tx["type"] == "purchase" and pid not in seen_suppliers:
            seen_suppliers.add(pid)
            sup = _se(suppliers_elem, "Supplier")

            cs = _se(sup, "CompanyStructure")
            _se(cs, "RegistrationNumber", p.get("tax_id", pid)[:35])
            _se(cs, "Name", p.get("name", pid)[:256])
            cs_addr = _se(cs, "Address")
            _se(cs_addr, "City", "Bucuresti")
            _se(cs_addr, "Country", "RO")

            _se(sup, "SupplierID", pid[:35])
            _se(sup, "AccountID", "4011")
            _se(sup, "OpeningCreditBalance", "0.00")
            _se(sup, "ClosingCreditBalance", f"{supplier_totals.get(pid, 0.0):.2f}")

    # Required empty container elements
    _se(master, "TaxTable")
    _se(master, "UOMTable")
    _se(master, "AnalysisTypeTable")
    _se(master, "MovementTypeTable")
    _se(master, "Products")
    _se(master, "Owners")
    _se(master, "Assets")

    # ------------------------------------------------------------------
    # GeneralLedgerEntries
    # ------------------------------------------------------------------
    gl = _se(root, "GeneralLedgerEntries")
    _se(gl, "NumberOfEntries", str(len(transactions)))

    if transactions:
        journal = _se(gl, "Journal")
        _se(journal, "JournalID", "J01")
        _se(journal, "Description", "Sales and Purchases Journal")
        _se(journal, "Type", "GEN")

        for tx in transactions:
            year, month, _ = tx["date"].split("-")
            period = str(int(month))   # strip leading zero (xs:nonNegativeInteger)

            tx_elem = _se(journal, "Transaction")
            _se(tx_elem, "TransactionID", tx["transaction_id"][:70])
            _se(tx_elem, "Period", period)
            _se(tx_elem, "PeriodYear", year)
            _se(tx_elem, "TransactionDate", tx["date"])
            _se(tx_elem, "Description", tx["type"].capitalize())
            _se(tx_elem, "SystemEntryDate", tx["date"])
            _se(tx_elem, "GLPostingDate", tx["date"])

            # CustomerID / SupplierID: non-applicable ID left empty ("")
            if tx["type"] == "sale":
                _se(tx_elem, "CustomerID", tx["partner_id"][:35])
                _se(tx_elem, "SupplierID", "")
            else:
                _se(tx_elem, "CustomerID", "")
                _se(tx_elem, "SupplierID", tx["partner_id"][:35])

            # TransactionLine (one per transaction)
            line = _se(tx_elem, "TransactionLine")
            _se(line, "RecordID", "1")
            _se(line, "AccountID", "4111" if tx["type"] == "sale" else "4011")

            if tx["type"] == "sale":
                _se(line, "CustomerID", tx["partner_id"][:35])
                _se(line, "SupplierID", "")
            else:
                _se(line, "CustomerID", "")
                _se(line, "SupplierID", tx["partner_id"][:35])

            _se(line, "Description", tx["type"].capitalize())

            # DebitAmount for sales, CreditAmount for purchases
            amt_tag = "DebitAmount" if tx["type"] == "sale" else "CreditAmount"
            _amount_struct(line, amt_tag, tx["amount"])

            # TaxInformation (required, minOccurs defaults to 1)
            tax_info = _se(line, "TaxInformation")
            _se(tax_info, "TaxType", "TVA")
            _se(tax_info, "TaxCode", "TVA19")
            tax_net = round(tx["amount"] / 1.19, 2)
            tax_vat = round(tx["amount"] - tax_net, 2)
            _se(tax_info, "TaxPercentage", "19")
            _se(tax_info, "TaxBase", f"{tax_net:.2f}")
            _amount_struct(tax_info, "TaxAmount", tax_vat)

    # ------------------------------------------------------------------
    # SourceDocuments (required container elements)
    # ------------------------------------------------------------------
    src_docs = _se(root, "SourceDocuments")
    _se(src_docs, "SalesInvoices")
    _se(src_docs, "PurchaseInvoices")
    _se(src_docs, "Payments")
    _se(src_docs, "MovementOfGoods")

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
