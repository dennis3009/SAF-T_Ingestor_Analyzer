"""
parser.py - XML to JSON/CSV transformer.

Reads all SAF-T XML files from data/raw_xml/, extracts companies, partners,
and transactions, then normalises them into:
  - data/json/companies.json
  - data/json/partners.json
  - data/csv/transactions.csv
"""

import os
import json
import csv
import xml.etree.ElementTree as ET

RAW_XML_DIR = os.path.join(os.path.dirname(__file__), "data", "raw_xml")
JSON_DIR = os.path.join(os.path.dirname(__file__), "data", "json")
CSV_DIR = os.path.join(os.path.dirname(__file__), "data", "csv")

# Official ANAF SAF-T v2.48 namespace
NAMESPACE = "mfp:anaf:dgti:d406t:declaratie:v1"
NS = {"s": NAMESPACE}


def _tag(name: str) -> str:
    """Return fully-qualified tag with namespace."""
    return f"{{{NAMESPACE}}}{name}"


def _text(elem, tag: str, default: str = "") -> str:
    """Safely extract text from a direct child element."""
    child = elem.find(_tag(tag))
    return child.text.strip() if child is not None and child.text else default


def parse(
    raw_dir: str = RAW_XML_DIR,
    json_dir: str = JSON_DIR,
    csv_dir: str = CSV_DIR,
) -> tuple:
    """
    Parse all XML files and produce normalised JSON and CSV outputs.

    Returns:
        (companies_dict, partners_dict, transactions_list)
    """
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)

    companies: dict = {}   # company_id -> dict
    partners: dict = {}    # partner_id -> dict
    transactions: list = []

    xml_files = sorted(
        f for f in os.listdir(raw_dir) if f.lower().endswith(".xml")
    )
    if not xml_files:
        raise FileNotFoundError(f"No XML files found in {raw_dir}")

    for filename in xml_files:
        filepath = os.path.join(raw_dir, filename)
        try:
            tree = ET.parse(filepath)
        except ET.ParseError as exc:
            print(f"[parser] WARNING: Could not parse {filename}: {exc}")
            continue

        root = tree.getroot()
        current_company_id = ""

        # --- Header / Company ---
        header = root.find(_tag("Header"))
        if header is not None:
            company_elem = header.find(_tag("Company"))
            if company_elem is not None:
                # RegistrationNumber stores the company["id"] (e.g. "COMP0001")
                cid = _text(company_elem, "RegistrationNumber")
                if cid:
                    current_company_id = cid
                    if cid not in companies:
                        companies[cid] = {
                            "company_id": cid,
                            "name": _text(company_elem, "Name"),
                            "tax_id": cid,
                        }

        # --- MasterFiles: Customers ---
        master = root.find(_tag("MasterFiles"))
        if master is not None:
            customers_elem = master.find(_tag("Customers"))
            if customers_elem is not None:
                for cust in customers_elem.findall(_tag("Customer")):
                    pid = _text(cust, "CustomerID")
                    if pid and pid not in partners:
                        cs = cust.find(_tag("CompanyStructure"))
                        if cs is not None:
                            name = _text(cs, "Name")
                            tax_id = _text(cs, "RegistrationNumber")
                        else:
                            name = pid
                            tax_id = ""
                        partners[pid] = {
                            "partner_id": pid,
                            "name": name,
                            "tax_id": tax_id,
                            "type": "customer",
                        }

            suppliers_elem = master.find(_tag("Suppliers"))
            if suppliers_elem is not None:
                for sup in suppliers_elem.findall(_tag("Supplier")):
                    pid = _text(sup, "SupplierID")
                    if pid and pid not in partners:
                        cs = sup.find(_tag("CompanyStructure"))
                        if cs is not None:
                            name = _text(cs, "Name")
                            tax_id = _text(cs, "RegistrationNumber")
                        else:
                            name = pid
                            tax_id = ""
                        partners[pid] = {
                            "partner_id": pid,
                            "name": name,
                            "tax_id": tax_id,
                            "type": "supplier",
                        }

        # --- GeneralLedgerEntries → Journal → Transaction ---
        gl = root.find(_tag("GeneralLedgerEntries"))
        if gl is not None:
            for journal in gl.findall(_tag("Journal")):
                for tx_elem in journal.findall(_tag("Transaction")):
                    customer_id = _text(tx_elem, "CustomerID")
                    supplier_id = _text(tx_elem, "SupplierID")
                    tx_type = "sale" if customer_id else "purchase"
                    partner_id = customer_id if customer_id else supplier_id

                    # Amount from the first TransactionLine's Debit/CreditAmount
                    amount = ""
                    line = tx_elem.find(_tag("TransactionLine"))
                    if line is not None:
                        for amount_tag in ("DebitAmount", "CreditAmount"):
                            amt_container = line.find(_tag(amount_tag))
                            if amt_container is not None:
                                amt_elem = amt_container.find(_tag("Amount"))
                                if amt_elem is not None and amt_elem.text:
                                    amount = amt_elem.text.strip()
                                break

                    tx = {
                        "transaction_id": _text(tx_elem, "TransactionID"),
                        "company_id": current_company_id,
                        "partner_id": partner_id,
                        "amount": amount,
                        "date": _text(tx_elem, "TransactionDate"),
                        "type": tx_type,
                    }
                    if tx["transaction_id"]:
                        transactions.append(tx)

    # --- Write companies.json ---
    companies_path = os.path.join(json_dir, "companies.json")
    with open(companies_path, "w", encoding="utf-8") as fh:
        json.dump(list(companies.values()), fh, indent=2, ensure_ascii=False)

    # --- Write partners.json ---
    partners_path = os.path.join(json_dir, "partners.json")
    with open(partners_path, "w", encoding="utf-8") as fh:
        json.dump(list(partners.values()), fh, indent=2, ensure_ascii=False)

    # --- Write transactions.csv ---
    tx_path = os.path.join(csv_dir, "transactions.csv")
    fieldnames = ["transaction_id", "company_id", "partner_id",
                  "amount", "date", "type"]
    with open(tx_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)

    print(
        f"[parser] Parsed {len(xml_files)} files → "
        f"{len(companies)} companies, "
        f"{len(partners)} partners, "
        f"{len(transactions)} transactions"
    )
    return companies, partners, transactions


if __name__ == "__main__":
    parse()
