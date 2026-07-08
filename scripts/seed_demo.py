#!/usr/bin/env python
"""
Demo data seed script.

Creates:
  - 5 Clients
  - 8 Sites
  - 8 DG Sets
  - 6 Inventory Categories
  - 50 Inventory Items
  - 20 Tickets (various statuses / priorities)
  - 30 Inventory Dispatches linked to tickets

Usage (inside container):
    python scripts/seed_demo.py

Usage (from host):
    docker exec opsly-app-1 sh -c "cd /app && python scripts/seed_demo.py"

Safe to re-run — skips any record that already exists (by unique key).
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import SessionLocal


# ─── helpers ──────────────────────────────────────────────────────────────────

def now() -> datetime:
    return datetime.now(timezone.utc)

def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)

def uid() -> uuid.UUID:
    return uuid.uuid4()


# ─── main ─────────────────────────────────────────────────────────────────────

def seed() -> None:  # noqa: C901
    db = SessionLocal()
    try:
        from app.models.user import User
        from app.models.client import Client
        from app.models.inventory import InventoryCategory, InventoryItem, InventoryDispatch
        from app.models.ticket import TicketStatus, TicketPriority
        import sqlalchemy as sa
        owner = db.query(User).filter(User.email == "owner@opsly.local").first()
        mod   = db.query(User).filter(User.email == "mod@opsly.local").first()
        staff = db.query(User).filter(User.email == "staff@opsly.local").first()

        if not owner:
            print("[ERROR] Seed users not found. Run seed.py first.")
            return

        # ── CLIENTS ──────────────────────────────────────────────────────────
        clients_data = [
            ("Tata Power Ltd",          "Ramesh Iyer",    "tata.power@client.local",     "9811000001", "Mumbai, Maharashtra"),
            ("Adani Infra Pvt Ltd",      "Sunita Sharma",  "adani.infra@client.local",    "9811000002", "Ahmedabad, Gujarat"),
            ("Reliance Retail Ltd",      "Vikram Nair",    "reliance.retail@client.local","9811000003", "Navi Mumbai, Maharashtra"),
            ("Mahindra Logistics",       "Pooja Desai",    "mahindra.log@client.local",   "9811000004", "Pune, Maharashtra"),
            ("NTPC Green Energy",        "Arvind Tiwari",  "ntpc.green@client.local",     "9811000005", "New Delhi, Delhi"),
        ]

        clients: list[Client] = []
        for name, cp, email, phone, addr in clients_data:
            existing = db.query(Client).filter(Client.email == email).first()
            if existing:
                clients.append(existing)
            else:
                c = Client(id=uid(), name=name, contact_person=cp,
                           email=email, phone=phone, address=addr)
                db.add(c)
                db.flush()
                clients.append(c)

        # ── SITES ────────────────────────────────────────────────────────────
        # Use raw SQL to avoid ORM model mismatch (model has pincode/gps, DB has contact_name/phone)
        sites_data = [
            ("Tata Power — Dharavi Substation",   "Dharavi, Mumbai",        "Mumbai",             "Maharashtra", clients[0], "Ramesh Iyer",    "9811000001"),
            ("Adani Infra — Mundra Yard",          "Mundra Industrial Area", "Kutch",              "Gujarat",     clients[1], "Sunita Sharma",  "9811000002"),
            ("Reliance Retail — Ghansoli DC",      "Ghansoli, Navi Mumbai",  "Navi Mumbai",        "Maharashtra", clients[2], "Vikram Nair",    "9811000003"),
            ("Mahindra Logistics — Pune Hub",      "Chakan, Pune",           "Pune",               "Maharashtra", clients[3], "Pooja Desai",    "9811000004"),
            ("NTPC Green — Dadri Plant",           "Dadri, Greater Noida",   "Gautam Buddh Nagar", "UP",          clients[4], "Arvind Tiwari",  "9811000005"),
            ("Tata Power — Trombay HQ",            "Trombay, Mumbai",        "Mumbai",             "Maharashtra", clients[0], "Ramesh Iyer",    "9811000001"),
            ("Adani Infra — Hazira Terminal",      "Hazira, Surat",          "Surat",              "Gujarat",     clients[1], "Sunita Sharma",  "9811000002"),
            ("Reliance Retail — Nagpur WH",        "Butibori, Nagpur",       "Nagpur",             "Maharashtra", clients[2], "Vikram Nair",    "9811000003"),
        ]

        site_ids: list[uuid.UUID] = []
        for name, addr, city, state, client, contact_name, contact_phone in sites_data:
            row = db.execute(
                sa.text("SELECT id FROM sites WHERE name = :name AND is_deleted = false LIMIT 1"),
                {"name": name},
            ).fetchone()
            if row:
                site_ids.append(row[0])
            else:
                new_id = uid()
                db.execute(
                    sa.text(
                        "INSERT INTO sites (id, name, address, city, state, contact_name, contact_phone, client_id) "
                        "VALUES (:id, :name, :address, :city, :state, :contact_name, :contact_phone, :client_id)"
                    ),
                    {"id": new_id, "name": name, "address": addr, "city": city, "state": state,
                     "contact_name": contact_name, "contact_phone": contact_phone, "client_id": client.id},
                )
                site_ids.append(new_id)

        # ── DG SETS ──────────────────────────────────────────────────────────
        # Use raw SQL — model has capacity_kva/service dates but DB also requires asset_tag (NOT NULL)
        dg_data = [
            (site_ids[0], "Kirloskar",  "KG1-750AS",   750,  "KIR-2019-00101", "ASSET-KIR-001", date(2019, 3, 10), date(2025, 12, 1),  date(2026, 3, 1),  date(2027, 3, 10)),
            (site_ids[1], "Cummins",    "C750D5",       750,  "CUM-2020-00202", "ASSET-CUM-002", date(2020, 6, 15), date(2025, 11, 5),  date(2026, 2, 5),  date(2026, 6, 15)),
            (site_ids[2], "Mahindra",   "mPower-500",   500,  "MAH-2021-00303", "ASSET-MAH-003", date(2021, 1, 20), date(2026, 1, 10),  date(2026, 4, 10), date(2027, 1, 20)),
            (site_ids[3], "Volvo Penta","TAD1345GE",    1000, "VOL-2018-00404", "ASSET-VOL-004", date(2018, 9, 5),  date(2025, 10, 20), date(2026, 1, 20), date(2026, 9, 5)),
            (site_ids[4], "KOEL",       "KG2-2000AS",   2000, "KOE-2022-00505", "ASSET-KOE-005", date(2022, 4, 1),  date(2026, 2, 14),  date(2026, 5, 14), date(2028, 4, 1)),
            (site_ids[5], "Cummins",    "C500D5",       500,  "CUM-2020-00606", "ASSET-CUM-006", date(2020, 11, 8), date(2025, 9, 22),  date(2025, 12, 22),date(2026, 11, 8)),
            (site_ids[6], "Caterpillar","3412C",        1500, "CAT-2017-00707", "ASSET-CAT-007", date(2017, 7, 30), date(2025, 8, 18),  date(2025, 11, 18),date(2025, 7, 30)),
            (site_ids[7], "Kirloskar",  "KG-250AS",     250,  "KIR-2023-00808", "ASSET-KIR-008", date(2023, 2, 14), date(2026, 1, 25),  date(2026, 4, 25), date(2029, 2, 14)),
        ]

        dg_ids: list[uuid.UUID] = []
        for site_id, make, model, kva, serial, asset_tag, inst, last_svc, next_svc, amc in dg_data:
            row = db.execute(
                sa.text("SELECT id FROM dg_sets WHERE serial_no = :serial LIMIT 1"),
                {"serial": serial},
            ).fetchone()
            if row:
                dg_ids.append(row[0])
            else:
                new_id = uid()
                db.execute(
                    sa.text(
                        "INSERT INTO dg_sets (id, site_id, make, model, capacity_kva, serial_no, asset_tag, "
                        "installation_date, last_service_date, next_service_date, amc_expiry, service_interval_days) "
                        "VALUES (:id, :site_id, :make, :model, :kva, :serial, :asset_tag, "
                        ":inst, :last_svc, :next_svc, :amc, 90)"
                    ),
                    {"id": new_id, "site_id": site_id, "make": make, "model": model,
                     "kva": kva, "serial": serial, "asset_tag": asset_tag,
                     "inst": inst, "last_svc": last_svc, "next_svc": next_svc, "amc": amc},
                )
                dg_ids.append(new_id)

        # ── INVENTORY CATEGORIES ─────────────────────────────────────────────
        cat_data = [
            ("AVR / Voltage Regulator", "Automatic voltage regulators and control boards"),
            ("Battery & Charging",      "Batteries, battery chargers, and UPS units"),
            ("Cooling System",          "Radiators, coolant, fans, thermostats, water pumps"),
            ("Fuel System",             "Fuel filters, injectors, transfer pumps, fuel pipes"),
            ("Electrical & Wiring",     "Cables, contactors, MCBs, relays, control panels"),
            ("Mechanical & Engine",     "Engine oil, oil filters, belts, gaskets, spare parts"),
        ]

        categories: list[InventoryCategory] = []
        for cname, cdesc in cat_data:
            existing = db.query(InventoryCategory).filter(
                InventoryCategory.category_name == cname).first()
            if existing:
                categories.append(existing)
            else:
                cat = InventoryCategory(id=uid(), category_name=cname, description=cdesc)
                db.add(cat)
                db.flush()
                categories.append(cat)

        cat_avr, cat_bat, cat_cool, cat_fuel, cat_elec, cat_mech = categories

        # ── INVENTORY ITEMS (50) ─────────────────────────────────────────────
        # (part_name, part_number, barcode, unit_cost, quantity, low_stock_threshold, category)
        items_data = [
            # AVR / Voltage Regulator (8 items)
            ("AVR Module — Stamford MX321",    "AVR-MX321-01",  "BC-AVR-001", 4200.00, 12,  3, cat_avr),
            ("AVR Module — Leroy Somer D350",  "AVR-D350-02",   "BC-AVR-002", 5800.00,  8,  3, cat_avr),
            ("Voltage Regulator Board — KOEL", "AVR-KOEL-03",   "BC-AVR-003", 3500.00,  6,  2, cat_avr),
            ("AVR Module — Cummins A041E662",  "AVR-A041E662",  "BC-AVR-004", 6700.00,  4,  2, cat_avr),
            ("Control Panel PCB — Kirloskar",  "PCB-KIR-05",    "BC-AVR-005", 8900.00,  5,  2, cat_avr),
            ("Exciter Diode Kit (6-pack)",      "DIODE-KIT-06",  "BC-AVR-006",  620.00, 30,  8, cat_avr),
            ("Voltage Sensing Relay",           "VSR-07",        "BC-AVR-007", 1450.00, 14,  5, cat_avr),
            ("AVR Potentiometer Assembly",      "AVR-POT-08",    "BC-AVR-008",  380.00, 20,  5, cat_avr),

            # Battery & Charging (8 items)
            ("Battery — Exide 12V 150Ah",      "BAT-EX150-09",  "BC-BAT-009", 12500.00,  9,  3, cat_bat),
            ("Battery — Amaron 12V 200Ah",     "BAT-AM200-10",  "BC-BAT-010", 16800.00,  6,  2, cat_bat),
            ("Battery Charger — 24V 20A",      "CHR-24V20A-11", "BC-BAT-011",  4300.00,  7,  2, cat_bat),
            ("Battery Equalizer Module",       "BEQ-12V-12",    "BC-BAT-012",  1850.00, 11,  4, cat_bat),
            ("Battery Terminal Clamp Set",     None,            "BC-BAT-013",   280.00, 40, 10, cat_bat),
            ("Electrolyte Refill Kit 5L",      None,            "BC-BAT-014",   520.00, 18,  5, cat_bat),
            ("UPS Battery Pack — 48V 100Ah",   "UPS-BP4810-15", "BC-BAT-015", 28000.00,  3,  1, cat_bat),
            ("Battery Hydrometer",             None,            "BC-BAT-016",   195.00, 25,  8, cat_bat),

            # Cooling System (8 items)
            ("Radiator — Kirloskar KG1-750",   "RAD-KIR750-17", "BC-COL-017", 18500.00,  3,  1, cat_cool),
            ("Radiator — Cummins C750",        "RAD-CUM750-18", "BC-COL-018", 21000.00,  2,  1, cat_cool),
            ("Coolant Thermostat 83°C",        "THERM-83-19",   "BC-COL-019",   760.00, 22,  5, cat_cool),
            ("Water Pump Seal Kit",            "WPS-KIT-20",    "BC-COL-020",   480.00, 15,  5, cat_cool),
            ("Radiator Hose — Upper",          None,            "BC-COL-021",   340.00, 28,  8, cat_cool),
            ("Radiator Hose — Lower",          None,            "BC-COL-022",   310.00, 28,  8, cat_cool),
            ("Antifreeze Coolant 20L",         "COOL-AF20L-23", "BC-COL-023",  1200.00, 10,  3, cat_cool),
            ("Cooling Fan Belt — A-section",   None,            "BC-COL-024",   220.00, 35, 10, cat_cool),

            # Fuel System (9 items)
            ("Primary Fuel Filter — Racor 500", "FF-RAC500-25", "BC-FUL-025",  1650.00, 18,  5, cat_fuel),
            ("Secondary Fuel Filter — Cummins", "FF-CUM-26",    "BC-FUL-026",   980.00, 20,  5, cat_fuel),
            ("Fuel Injector — Bosch 4-hole",    "INJ-BSH4H-27", "BC-FUL-027",  4200.00,  6,  2, cat_fuel),
            ("Fuel Transfer Pump — 24V",        "FTP-24V-28",   "BC-FUL-028",  3100.00,  5,  2, cat_fuel),
            ("Fuel Pipe — High Pressure 60cm",  None,           "BC-FUL-029",   420.00, 24,  8, cat_fuel),
            ("Fuel Solenoid Valve 12V",         "FSV-12V-30",   "BC-FUL-030",  1200.00, 12,  4, cat_fuel),
            ("Lift Pump — Diesel",              "LP-DSL-31",    "BC-FUL-031",  2800.00,  7,  2, cat_fuel),
            ("Fuel Tank Breather Valve",        None,           "BC-FUL-032",   380.00, 20,  6, cat_fuel),
            ("Fuel Level Sender Unit",          "FLS-32-33",    "BC-FUL-033",   950.00,  9,  3, cat_fuel),

            # Electrical & Wiring (9 items)
            ("MCB 63A — Schneider",             "MCB-63A-34",   "BC-ELC-034",   850.00, 16,  5, cat_elec),
            ("Contactor 40A — L&T",             "CTR-40A-35",   "BC-ELC-035",  1200.00, 12,  4, cat_elec),
            ("Control Cable 1.5mm 50m",         None,           "BC-ELC-036",  2800.00,  5,  2, cat_elec),
            ("Power Cable 10mm 50m",            None,           "BC-ELC-037",  6500.00,  4,  1, cat_elec),
            ("Relay SPDT 24V",                  "RLY-SPDT24-38","BC-ELC-038",   280.00, 40, 10, cat_elec),
            ("Earth Clamp Kit",                 None,           "BC-ELC-039",   350.00, 18,  5, cat_elec),
            ("Terminal Block 10-way",           None,           "BC-ELC-040",   190.00, 30,  8, cat_elec),
            ("Fuse 50A HRC",                    None,           "BC-ELC-041",   120.00, 60, 15, cat_elec),
            ("Control Panel Lamp 24V LED",      None,           "BC-ELC-042",    85.00, 50, 15, cat_elec),

            # Mechanical & Engine (8 items)
            ("Engine Oil SAE 15W-40 20L",       "OIL-15W40-43", "BC-MCH-043",  4200.00, 14,  4, cat_mech),
            ("Oil Filter — Cummins LF9009",     "OF-CUM9009-44","BC-MCH-044",   650.00, 20,  6, cat_mech),
            ("Oil Filter — Kirloskar KOF",      "OF-KIR-45",    "BC-MCH-045",   580.00, 18,  6, cat_mech),
            ("Air Filter Primary",              "AF-PRI-46",    "BC-MCH-046",   920.00, 15,  5, cat_mech),
            ("Air Filter Secondary",            "AF-SEC-47",    "BC-MCH-047",   680.00, 12,  4, cat_mech),
            ("Valve Cover Gasket",              None,           "BC-MCH-048",   480.00, 10,  3, cat_mech),
            ("Drive Belt — Alternator",         None,           "BC-MCH-049",   360.00, 22,  6, cat_mech),
            ("Engine Mount — Anti-vibration",   "EM-ANTIVIB-50","BC-MCH-050",  1800.00,  8,  3, cat_mech),
        ]

        items: list[InventoryItem] = []
        for part_name, part_no, barcode, cost, qty, threshold, cat in items_data:
            # check by barcode (unique) to avoid duplicates
            existing = db.query(InventoryItem).filter(InventoryItem.barcode == barcode).first()
            if existing:
                items.append(existing)
            else:
                item = InventoryItem(
                    id=uid(), part_name=part_name, part_number=part_no,
                    barcode=barcode, unit_cost=cost, quantity=qty,
                    low_stock_threshold=threshold, category_id=cat.id,
                )
                db.add(item)
                db.flush()
                items.append(item)

        # ── TICKETS (20) ─────────────────────────────────────────────────────
        # (reference_no, dg_idx, status, priority, issue, notes, days_ago_created)
        tickets_data = [
            # Completed tickets
            ("TKT-2026-001", 0, TicketStatus.COMPLETED, TicketPriority.HIGH,
             "AVR failure — no output voltage on Phase B",
             "AVR module replaced. Load test passed at 80% capacity.", 28),
            ("TKT-2026-002", 1, TicketStatus.COMPLETED, TicketPriority.MEDIUM,
             "Scheduled 250-hour service — oil & filter change",
             "Oil changed, filters replaced. All checks nominal.", 22),
            ("TKT-2026-003", 2, TicketStatus.COMPLETED, TicketPriority.HIGH,
             "Battery not holding charge — DG fails to start on 3rd attempt",
             "Both batteries replaced. Charger voltage adjusted to 27.6V.", 18),
            ("TKT-2026-004", 3, TicketStatus.COMPLETED, TicketPriority.CRITICAL,
             "Radiator coolant leak — DG overheating at 75% load",
             "Radiator replaced, coolant flush done, thermostat replaced.", 15),
            ("TKT-2026-005", 5, TicketStatus.COMPLETED, TicketPriority.LOW,
             "Annual AMC inspection visit",
             "All parameters within spec. Lubrication done.", 12),

            # In-progress tickets
            ("TKT-2026-006", 4, TicketStatus.IN_PROGRESS, TicketPriority.HIGH,
             "Fuel injector #3 misfiring — excessive black smoke under load",
             None, 5),
            ("TKT-2026-007", 6, TicketStatus.IN_PROGRESS, TicketPriority.MEDIUM,
             "Control panel lamp failures and relay chatter on start",
             None, 4),
            ("TKT-2026-008", 7, TicketStatus.IN_PROGRESS, TicketPriority.MEDIUM,
             "Scheduled 500-hour service — full mechanical check",
             None, 3),

            # Waiting for parts
            ("TKT-2026-009", 6, TicketStatus.WAITING_FOR_PARTS, TicketPriority.CRITICAL,
             "Catastrophic coolant leak — cracked radiator header tank",
             "Sourcing Caterpillar 3412C radiator. DG offline.", 6),
            ("TKT-2026-010", 3, TicketStatus.WAITING_FOR_PARTS, TicketPriority.HIGH,
             "Fuel transfer pump seized — DG runs on gravity feed only",
             "Pump ordered from Volvo Penta dealer.", 3),

            # Assigned / En-route
            ("TKT-2026-011", 0, TicketStatus.ASSIGNED, TicketPriority.MEDIUM,
             "Quarterly load bank test required by site SLA",
             None, 2),
            ("TKT-2026-012", 2, TicketStatus.EN_ROUTE, TicketPriority.HIGH,
             "DG fails to auto-start on mains failure — AMF fault",
             None, 1),
            ("TKT-2026-013", 1, TicketStatus.EN_ROUTE, TicketPriority.MEDIUM,
             "Air filter choked — high crankcase pressure alarm",
             None, 1),

            # Open tickets
            ("TKT-2026-014", 4, TicketStatus.OPEN, TicketPriority.LOW,
             "Oil level sensor reading erratic — possible wiring fault",
             None, 0),
            ("TKT-2026-015", 5, TicketStatus.OPEN, TicketPriority.MEDIUM,
             "Alternator output fluctuation — suspected AVR issue",
             None, 0),
            ("TKT-2026-016", 7, TicketStatus.OPEN, TicketPriority.HIGH,
             "Emergency: DG tripped on high coolant temperature alarm",
             None, 0),
            ("TKT-2026-017", 2, TicketStatus.OPEN, TicketPriority.LOW,
             "Drive belt showing wear — proactive replacement before next service",
             None, 0),
            ("TKT-2026-018", 0, TicketStatus.OPEN, TicketPriority.MEDIUM,
             "MCB trips intermittently under full load — suspected thermal overload",
             None, 0),

            # Invoiced
            ("TKT-2026-019", 1, TicketStatus.INVOICED, TicketPriority.MEDIUM,
             "Half-yearly service + battery top-up",
             "Invoice #INV-2026-019 raised on 20 Mar 2026.", 20),
            ("TKT-2026-020", 3, TicketStatus.INVOICED, TicketPriority.HIGH,
             "Emergency breakdown — contactor failure on ATS panel",
             "Invoice #INV-2026-020 raised on 15 Mar 2026.", 25),
        ]

        ticket_ids: dict[str, uuid.UUID] = {}
        for ref, dg_idx, status, priority, issue, notes, dago in tickets_data:
            existing = db.execute(
                sa.text("SELECT id FROM tickets WHERE reference_no = :ref LIMIT 1"),
                {"ref": ref},
            ).fetchone()
            if existing:
                ticket_ids[ref] = existing[0]
                continue

            created   = days_ago(dago)
            completed = created + timedelta(days=2) if status in (
                TicketStatus.COMPLETED, TicketStatus.INVOICED) else None
            invoiced_at = completed + timedelta(days=1) if status == TicketStatus.INVOICED else None
            dg_id     = dg_ids[dg_idx]
            site_id   = site_ids[dg_idx]
            t_id      = uid()

            db.execute(
                sa.text(
                    "INSERT INTO tickets "
                    "(id, reference_no, dg_set_id, site_id, created_by, status, priority, "
                    "reported_issue, notes, completed_at, invoiced_at) "
                    "VALUES (:id, :ref, :dg, :site, :creator, :status, :priority, "
                    ":issue, :notes, :completed, :invoiced)"
                ),
                {"id": t_id, "ref": ref, "dg": dg_id, "site": site_id,
                 "creator": owner.id, "status": status.value, "priority": priority.value,
                 "issue": issue, "notes": notes, "completed": completed, "invoiced": invoiced_at},
            )
            # backdate created_at
            db.execute(
                sa.text("UPDATE tickets SET created_at = :ts WHERE id = :id"),
                {"ts": created, "id": t_id},
            )

            # assign technicians via junction table
            db.execute(
                sa.text("INSERT INTO ticket_technicians (ticket_id, user_id) VALUES (:tid, :uid)"),
                {"tid": t_id, "uid": staff.id},
            )
            if status in (TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED, TicketStatus.INVOICED):
                db.execute(
                    sa.text("INSERT INTO ticket_technicians (ticket_id, user_id) VALUES (:tid, :uid)"),
                    {"tid": t_id, "uid": mod.id},
                )

            # status history
            db.execute(
                sa.text(
                    "INSERT INTO ticket_status_history "
                    "(id, ticket_id, from_status, to_status, changed_by, changed_at) "
                    "VALUES (:id, :tid, NULL, :status, :by, :at)"
                ),
                {"id": uid(), "tid": t_id, "status": status.value,
                 "by": owner.id, "at": created},
            )
            ticket_ids[ref] = t_id

        # ── INVENTORY DISPATCHES (30) ─────────────────────────────────────────
        # Link inventory items to completed / in-progress tickets
        # (ticket_ref, item_barcode, qty, notes, returned_qty, days_since_dispatch)
        dispatches_data = [
            # TKT-2026-001 (AVR replacement — completed)
            ("TKT-2026-001", "BC-AVR-001", 1, "Replaced failed MX321 AVR module",         1,  26),
            ("TKT-2026-001", "BC-ELC-041", 4, "Fuses blown on AVR supply rail",            0,  26),

            # TKT-2026-002 (Scheduled 250hr service — completed)
            ("TKT-2026-002", "BC-MCH-043", 1, "20L engine oil change",                    1,  20),
            ("TKT-2026-002", "BC-MCH-044", 1, "Cummins oil filter replaced",               1,  20),
            ("TKT-2026-002", "BC-FUL-025", 1, "Primary fuel filter replaced",              1,  20),
            ("TKT-2026-002", "BC-FUL-026", 1, "Secondary fuel filter replaced",            1,  20),

            # TKT-2026-003 (Battery failure — completed)
            ("TKT-2026-003", "BC-BAT-009", 2, "Both 150Ah batteries replaced",            2,  16),
            ("TKT-2026-003", "BC-BAT-013", 1, "Battery terminal clamp set replaced",      1,  16),

            # TKT-2026-004 (Radiator/coolant leak — completed)
            ("TKT-2026-004", "BC-COL-017", 1, "Radiator replaced (Kirloskar KG1-750)",    1,  13),
            ("TKT-2026-004", "BC-COL-019", 1, "Thermostat replaced at 83°C",              1,  13),
            ("TKT-2026-004", "BC-COL-023", 1, "Full coolant flush — 20L antifreeze",      1,  13),
            ("TKT-2026-004", "BC-COL-021", 2, "Upper radiator hoses replaced",            2,  13),

            # TKT-2026-005 (AMC inspection — completed)
            ("TKT-2026-005", "BC-MCH-047", 1, "Secondary air filter replaced",             1,  10),
            ("TKT-2026-005", "BC-COL-024", 1, "Fan belt replaced (worn)",                  1,  10),

            # TKT-2026-006 (Fuel injector misfire — in progress)
            ("TKT-2026-006", "BC-FUL-027", 1, "Bosch injector dispatched for #3 cylinder", 0,  3),
            ("TKT-2026-006", "BC-FUL-025", 1, "Fuel filter replaced as precaution",        1,  3),

            # TKT-2026-007 (Control panel / relay — in progress)
            ("TKT-2026-007", "BC-ELC-038", 3, "3x SPDT relays dispatched for panel",       0,  2),
            ("TKT-2026-007", "BC-ELC-042", 6, "LED lamps for control panel replaced",      6,  2),

            # TKT-2026-008 (500hr service — in progress)
            ("TKT-2026-008", "BC-MCH-043", 1, "Engine oil 20L",                            0,  1),
            ("TKT-2026-008", "BC-MCH-045", 1, "Kirloskar oil filter",                      0,  1),
            ("TKT-2026-008", "BC-MCH-046", 1, "Primary air filter",                        0,  1),

            # TKT-2026-019 (Invoiced — half yearly service)
            ("TKT-2026-019", "BC-MCH-043", 1, "Oil change",                                1,  18),
            ("TKT-2026-019", "BC-BAT-014", 1, "Electrolyte top-up kit",                    1,  18),

            # TKT-2026-020 (Invoiced — contactor failure)
            ("TKT-2026-020", "BC-ELC-035", 2, "Replaced 2x 40A L&T contactors",           2,  23),
            ("TKT-2026-020", "BC-ELC-034", 1, "MCB replaced",                              1,  23),
            ("TKT-2026-020", "BC-ELC-038", 2, "Control relays replaced",                   2,  23),

            # TKT-2026-009 (Waiting for parts — partial dispatch done)
            ("TKT-2026-009", "BC-COL-020", 1, "Water pump seal kit dispatched",            0,  4),

            # TKT-2026-010 (Waiting for parts — partial dispatch)
            ("TKT-2026-010", "BC-FUL-030", 1, "Fuel solenoid valve dispatched",            0,  2),

            # TKT-2026-012 (En-route — items staged)
            ("TKT-2026-012", "BC-AVR-008", 1, "AVR potentiometer staged for AMF repair",  0,  0),

            # TKT-2026-013 (En-route — air filter ready)
            ("TKT-2026-013", "BC-MCH-046", 1, "Primary air filter",                        0,  0),
            ("TKT-2026-013", "BC-MCH-047", 1, "Secondary air filter",                      0,  0),
        ]

        # build lookup maps
        item_map    = {i.barcode: i for i in items}

        dispatch_count = 0
        for t_ref, barcode, qty, notes, ret_qty, dago in dispatches_data:
            ticket_id = ticket_ids.get(t_ref)
            item      = item_map.get(barcode)
            if not ticket_id or not item:
                print(f"  [SKIP] dispatch {t_ref}/{barcode} — not found")
                continue

            # skip if already exists (idempotent)
            existing_d = db.query(InventoryDispatch).filter(
                InventoryDispatch.ticket_id == ticket_id,
                InventoryDispatch.inventory_item_id == item.id,
            ).first()
            if existing_d:
                continue

            dispatched_at = days_ago(dago)
            d = InventoryDispatch(
                id=uid(),
                inventory_item_id=item.id,
                ticket_id=ticket_id,
                quantity=qty,
                dispatched_by=owner.id,
                dispatched_at=dispatched_at,
                part_number_dispatched=item.part_number,
                barcode_dispatched=item.barcode,
                notes=notes,
                returned_quantity=ret_qty,
                returned_by=mod.id if ret_qty > 0 else None,
                returned_at=dispatched_at + timedelta(days=1) if ret_qty > 0 else None,
            )
            db.add(d)
            dispatch_count += 1

        db.commit()

        # ── SUMMARY ───────────────────────────────────────────────────────────
        total_items   = db.query(InventoryItem).count()
        total_cats    = db.query(InventoryCategory).count()
        total_tickets = db.execute(sa.text("SELECT COUNT(*) FROM tickets WHERE is_deleted = false")).scalar()
        total_disp    = db.query(InventoryDispatch).count()
        total_clients = db.query(Client).count()
        total_sites   = db.execute(sa.text("SELECT COUNT(*) FROM sites WHERE is_deleted = false")).scalar()
        total_dgs     = db.execute(sa.text("SELECT COUNT(*) FROM dg_sets WHERE is_deleted = false")).scalar()

        print("\n" + "=" * 60)
        print("  Opsly — Demo Seed Complete")
        print("=" * 60)
        print(f"  {'Clients':<28} {total_clients}")
        print(f"  {'Sites':<28} {total_sites}")
        print(f"  {'DG Sets':<28} {total_dgs}")
        print(f"  {'Inventory Categories':<28} {total_cats}")
        print(f"  {'Inventory Items':<28} {total_items}")
        print(f"  {'Tickets':<28} {total_tickets}")
        print(f"  {'Inventory Dispatches':<28} {total_disp}")
        print("=" * 60)
        print("\n  Login: owner@opsly.local / owner@123")
        print("=" * 60 + "\n")

    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Demo seed failed: {exc}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
