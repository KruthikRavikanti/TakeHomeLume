from __future__ import annotations

from typing import Dict, Optional

from src.schemas import AccountType, DriveRecord, DriveType, EmployeeRecord


EMPLOYEES: Dict[str, EmployeeRecord] = {
    "EMP-1042": EmployeeRecord(
        employee_id="EMP-1042",
        name="Sarah Chen",
        department="Product",
        team="Design",
        title="Senior Product Designer",
        manager_id="EMP-1060",
        manager_name="Jordan Rivera",
        office="San Francisco",
        work_email="sarah.chen@gaggia.example",
        work_phone="+1-415-555-0142",
        personal_email="sarah.chen.personal@example.com",
        personal_phone="+1-415-555-9102",
        home_address="1842 Valencia St, San Francisco, CA 94110",
        salary=152000,
        performance_rating="exceeds_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-1043": EmployeeRecord(
        employee_id="EMP-1043",
        name="David Kim",
        department="Engineering",
        team="Platform",
        title="Engineering Manager",
        manager_id="EMP-2200",
        manager_name="Priya Nair",
        office="New York",
        work_email="david.kim@gaggia.example",
        work_phone="+1-212-555-0143",
        personal_email="david.kim.personal@example.com",
        personal_phone="+1-917-555-9103",
        home_address="77 Hudson Ave, Brooklyn, NY 11201",
        salary=188000,
        performance_rating="meets_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-1060": EmployeeRecord(
        employee_id="EMP-1060",
        name="Jordan Rivera",
        department="Product",
        team="Design",
        title="Director of Product Design",
        manager_id="EMP-2011",
        manager_name="Maya Thompson",
        office="San Francisco",
        work_email="jordan.rivera@gaggia.example",
        work_phone="+1-415-555-0160",
        personal_email="jordan.rivera.personal@example.com",
        personal_phone="+1-415-555-9160",
        home_address="920 Dolores St, San Francisco, CA 94110",
        salary=221000,
        performance_rating="exceeds_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-7781": EmployeeRecord(
        employee_id="EMP-7781",
        name="Jessica Park",
        department="Finance",
        team="Corporate Finance",
        title="Finance Analyst",
        manager_id="EMP-1500",
        manager_name="Owen Brooks",
        office="Chicago",
        work_email="jessica.park@gaggia.example",
        work_phone="+1-312-555-7781",
        personal_email="jessica.park.personal@example.com",
        personal_phone="+1-312-555-9181",
        home_address="310 W Lake St, Chicago, IL 60606",
        salary=96000,
        performance_rating="needs_improvement",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-2011": EmployeeRecord(
        employee_id="EMP-2011",
        name="Maya Thompson",
        department="Product",
        team="Product Leadership",
        title="VP of Product",
        manager_id=None,
        manager_name=None,
        office="San Francisco",
        work_email="maya.thompson@gaggia.example",
        work_phone="+1-415-555-2011",
        personal_email="maya.thompson.personal@example.com",
        personal_phone="+1-415-555-9211",
        home_address="4 Presidio Ter, San Francisco, CA 94118",
        salary=310000,
        performance_rating="exceeds_expectations",
        employment_status="active",
        account_type=AccountType.EXECUTIVE,
    ),
    "EMP-1500": EmployeeRecord(
        employee_id="EMP-1500",
        name="Owen Brooks",
        department="Marketing",
        team="Growth Marketing",
        title="Marketing Director",
        manager_id=None,
        manager_name=None,
        office="Chicago",
        work_email="owen.brooks@gaggia.example",
        work_phone="+1-312-555-1500",
        personal_email="owen.brooks.personal@example.com",
        personal_phone="+1-312-555-9500",
        home_address="220 N Green St, Chicago, IL 60607",
        salary=176000,
        performance_rating="meets_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-2200": EmployeeRecord(
        employee_id="EMP-2200",
        name="Priya Nair",
        department="Engineering",
        team="Platform",
        title="Director of Engineering",
        manager_id=None,
        manager_name=None,
        office="New York",
        work_email="priya.nair@gaggia.example",
        work_phone="+1-212-555-2200",
        personal_email="priya.nair.personal@example.com",
        personal_phone="+1-646-555-9200",
        home_address="18 E 12th St, New York, NY 10003",
        salary=248000,
        performance_rating="exceeds_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-3300": EmployeeRecord(
        employee_id="EMP-3300",
        name="Lena Ortiz",
        department="Marketing",
        team="Brand Marketing",
        title="Marketing Specialist",
        manager_id="EMP-1500",
        manager_name="Owen Brooks",
        office="Austin",
        work_email="lena.ortiz@gaggia.example",
        work_phone="+1-512-555-3300",
        personal_email="lena.ortiz.personal@example.com",
        personal_phone="+1-512-555-9300",
        home_address="610 W 5th St, Austin, TX 78701",
        salary=84000,
        performance_rating="meets_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "EMP-4010": EmployeeRecord(
        employee_id="EMP-4010",
        name="Noah Patel",
        department="Engineering",
        team="DevOps",
        title="Senior DevOps Engineer",
        manager_id="EMP-2200",
        manager_name="Priya Nair",
        office="Remote",
        work_email="noah.patel@gaggia.example",
        work_phone="+1-628-555-4010",
        personal_email="noah.patel.personal@example.com",
        personal_phone="+1-628-555-9410",
        home_address="1250 Pearl St, Boulder, CO 80302",
        salary=171000,
        performance_rating="exceeds_expectations",
        employment_status="active",
        account_type=AccountType.ADMIN,
    ),
    "EMP-5500": EmployeeRecord(
        employee_id="EMP-5500",
        name="Avery Johnson",
        department="Sales",
        team="Enterprise Sales",
        title="Account Executive",
        manager_id=None,
        manager_name=None,
        office="Boston",
        work_email="avery.johnson@gaggia.example",
        work_phone="+1-617-555-5500",
        personal_email="avery.johnson.personal@example.com",
        personal_phone="+1-617-555-9500",
        home_address="45 Seaport Blvd, Boston, MA 02210",
        salary=132000,
        performance_rating="meets_expectations",
        employment_status="active",
        account_type=AccountType.STANDARD,
    ),
    "svc-deploy": EmployeeRecord(
        employee_id="svc-deploy",
        name="Deploy Service Account",
        department="Engineering",
        team="DevOps",
        title="CI/CD Service Account",
        manager_id="EMP-4010",
        manager_name="Noah Patel",
        office="System",
        work_email="svc-deploy@gaggia.example",
        work_phone="N/A",
        personal_email=None,
        personal_phone=None,
        home_address=None,
        salary=None,
        performance_rating=None,
        employment_status="active",
        account_type=AccountType.SERVICE,
    ),
    "sysadmin-01": EmployeeRecord(
        employee_id="sysadmin-01",
        name="System Administrator",
        department="IT",
        team="Infrastructure",
        title="Privileged Admin Account",
        manager_id="EMP-4010",
        manager_name="Noah Patel",
        office="System",
        work_email="sysadmin-01@gaggia.example",
        work_phone="N/A",
        personal_email=None,
        personal_phone=None,
        home_address=None,
        salary=None,
        performance_rating=None,
        employment_status="active",
        account_type=AccountType.ADMIN,
    ),
}


DRIVES: Dict[str, DriveRecord] = {
    "DRV-MKTG": DriveRecord(
        drive_id="DRV-MKTG",
        name="Marketing Shared Drive",
        drive_type=DriveType.TEAM,
        owning_team="Growth Marketing",
        owner_employee_id="EMP-1500",
    ),
    "DRV-DESIGN": DriveRecord(
        drive_id="DRV-DESIGN",
        name="Design Shared Drive",
        drive_type=DriveType.CROSS_TEAM,
        owning_team="Design",
        owner_employee_id="EMP-1060",
    ),
    "DRV-FIN-REST": DriveRecord(
        drive_id="DRV-FIN-REST",
        name="Finance Restricted Drive",
        drive_type=DriveType.RESTRICTED,
        owning_team="Corporate Finance",
        owner_employee_id="EMP-7781",
    ),
    "DRV-LEGAL-HOLD": DriveRecord(
        drive_id="DRV-LEGAL-HOLD",
        name="Legal-hold Investigation Drive",
        drive_type=DriveType.LEGAL_HOLD,
        owning_team="Legal",
        owner_employee_id=None,
    ),
    "DRV-JPARK-PERSONAL": DriveRecord(
        drive_id="DRV-JPARK-PERSONAL",
        name="Jessica Park Personal Drive",
        drive_type=DriveType.PERSONAL,
        owning_team="Corporate Finance",
        owner_employee_id="EMP-7781",
    ),
    "DRV-ENG": DriveRecord(
        drive_id="DRV-ENG",
        name="Engineering Shared Drive",
        drive_type=DriveType.TEAM,
        owning_team="Platform",
        owner_employee_id="EMP-2200",
    ),
}


def get_employee_by_id(employee_id: str) -> Optional[EmployeeRecord]:
    return EMPLOYEES.get(employee_id)


def find_employee(query: str) -> Optional[EmployeeRecord]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return None

    employee = EMPLOYEES.get(query)
    if employee:
        return employee

    for employee in EMPLOYEES.values():
        if normalized_query in employee.employee_id.lower():
            return employee
        if normalized_query in employee.name.lower():
            return employee
        if normalized_query in employee.work_email.lower():
            return employee

    return None


def get_drive_by_id_or_name(query: str) -> Optional[DriveRecord]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return None

    drive = DRIVES.get(query)
    if drive:
        return drive

    for drive in DRIVES.values():
        if normalized_query in drive.drive_id.lower():
            return drive
        if normalized_query in drive.name.lower():
            return drive

    return None


def is_in_reporting_chain(manager_id: str, employee_id: str) -> bool:
    current = get_employee_by_id(employee_id)
    visited = set()

    while current and current.manager_id and current.employee_id not in visited:
        if current.manager_id == manager_id:
            return True
        visited.add(current.employee_id)
        current = get_employee_by_id(current.manager_id)

    return False
