"""Command-line interface for Community Service Desk."""

import argparse
import sys

import uvicorn
from sqlalchemy.orm import Session

from community_service_desk.config import get_settings
from community_service_desk.database import SessionLocal, create_all_tables
from community_service_desk.models.conversation import AuthorType, EntryType, TicketConversation
from community_service_desk.models.event_history import EventType, TicketEventHistory
from community_service_desk.models.organization import Organization
from community_service_desk.models.queue import Queue
from community_service_desk.models.requester import Requester
from community_service_desk.models.resolution import TicketResolution, VerificationMethod
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import Membership, User
from community_service_desk.services.auth_service import AuthService
from community_service_desk.services.ticket_lifecycle import TicketStatus


def seed_database(db: Session):
    """Seed demo synthetic organization, members, and realistic sample tickets."""
    print("Seeding database with synthetic demo data...")

    # 1. Organization
    org = db.query(Organization).filter(Organization.slug == "metro-community").first()
    if not org:
        org = Organization(
            name="Metro Community Center",
            slug="metro-community",
            status="active",
        )
        db.add(org)
        db.flush()
        print(f"Created organization: {org.name} ({org.slug})")

    # 2. Users
    users_spec = [
        (
            "admin@metro-community.synthetic",
            "Sarah Admin (Demo)",
            "AdminPass123!",
            "organization_admin",
        ),
        ("agent@metro-community.synthetic", "Alex Support (Demo)", "AgentPass123!", "agent"),
        (
            "requester@metro-community.synthetic",
            "Jordan Requester (Demo)",
            "UserPass123!",
            "requester",
        ),
    ]

    users_by_email = {}
    for email, name, password, role in users_spec:
        u = db.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                email=email,
                display_name=name,
                password_hash=AuthService.hash_password(password),
                active=True,
            )
            db.add(u)
            db.flush()

        mem = (
            db.query(Membership)
            .filter(Membership.organization_id == org.id, Membership.user_id == u.id)
            .first()
        )
        if not mem:
            mem = Membership(
                organization_id=org.id,
                user_id=u.id,
                role=role,
            )
            db.add(mem)
        users_by_email[email] = u

    # 3. Queues
    queues_spec = [
        ("General Support", "General triage and non-technical inquiries"),
        ("IT & Devices", "Hardware, software, accounts, printers, and networking"),
        ("Facilities & Rooms", "Physical equipment, rooms, HVAC, and auditorium maintenance"),
    ]
    queues_by_name = {}
    for qname, qdesc in queues_spec:
        q = db.query(Queue).filter(Queue.organization_id == org.id, Queue.name == qname).first()
        if not q:
            q = Queue(organization_id=org.id, name=qname, description=qdesc, active=True)
            db.add(q)
            db.flush()
        queues_by_name[qname] = q

    # 4. Requester contact
    req_user = users_by_email["requester@metro-community.synthetic"]
    requester = (
        db.query(Requester)
        .filter(Requester.organization_id == org.id, Requester.email == req_user.email)
        .first()
    )
    if not requester:
        requester = Requester(
            organization_id=org.id,
            user_id=req_user.id,
            email=req_user.email,
            name=req_user.display_name,
            phone="555-019-2834",
            notes="Program coordinator for Room 204 youth workshops.",
        )
        db.add(requester)
        db.flush()

    agent_user = users_by_email["agent@metro-community.synthetic"]

    # 5. Synthetic Resolved Ticket 1 (Rich structured resolution)
    t1 = (
        db.query(Ticket)
        .filter(Ticket.organization_id == org.id, Ticket.ticket_number == "CSD-000001")
        .first()
    )
    if not t1:
        t1 = Ticket(
            organization_id=org.id,
            ticket_number="CSD-000001",
            requester_id=requester.id,
            title="[SYNTHETIC] Room 204 network printer mapping failed after workstation update",
            description="[SYNTHETIC] Staff reported printer \\printersrv\\room204-color vanished after Monday policy refresh.",
            status=TicketStatus.RESOLVED,
            priority="HIGH",
            category="Printing",
            tags=["windows", "printing", "policy", "synthetic"],
            queue_id=queues_by_name["IT & Devices"].id,
            assigned_agent_id=agent_user.id,
        )
        db.add(t1)
        db.flush()

        # Conversation entries
        c1 = TicketConversation(
            ticket_id=t1.id,
            author_id=req_user.id,
            author_name=req_user.display_name,
            author_type=AuthorType.REQUESTER,
            entry_type=EntryType.REQUESTER_VISIBLE_REPLY,
            body="Hi Alex, our color printer is missing from all computers in Room 204. Need to print workshop packets.",
        )
        c2 = TicketConversation(
            ticket_id=t1.id,
            author_id=agent_user.id,
            author_name=agent_user.display_name,
            author_type=AuthorType.AGENT,
            entry_type=EntryType.INTERNAL_NOTE,
            body="Investigated GPO event logs. Confirmed PrintNightmare hardening policy overrode mapped UNC connections.",
        )
        c3 = TicketConversation(
            ticket_id=t1.id,
            author_id=agent_user.id,
            author_name=agent_user.display_name,
            author_type=AuthorType.AGENT,
            entry_type=EntryType.REQUESTER_VISIBLE_REPLY,
            body="Restored the managed printer mapping in Room 204 and forced group policy refresh. Please test print.",
        )
        c4 = TicketConversation(
            ticket_id=t1.id,
            author_id=req_user.id,
            author_name=req_user.display_name,
            author_type=AuthorType.REQUESTER,
            entry_type=EntryType.REQUESTER_VISIBLE_REPLY,
            body="Test page printed successfully! Thank you so much.",
        )
        db.add_all([c1, c2, c3, c4])

        # Structured Resolution
        res1 = TicketResolution(
            ticket_id=t1.id,
            organization_id=org.id,
            resolved_by_id=agent_user.id,
            summary="Reinstalled the managed printer mapping and refreshed workstation group policy.",
            root_cause="Managed queue mapping was removed during automated GPO refresh.",
            resolution_steps="1. Opened print management console on DC.\n2. Re-linked GPO-Printers-Room204.\n3. Executed gpupdate /force on target stations.\n4. Verified spooler service.",
            verification=VerificationMethod.REQUESTER_CONFIRMED,
            knowledge_useful=True,
        )
        db.add(res1)

        db.add(
            TicketEventHistory(
                ticket_id=t1.id,
                actor_id=agent_user.id,
                actor_name=agent_user.display_name,
                actor_type="agent",
                event_type=EventType.RESOLUTION_RECORDED,
                old_value=None,
                new_value="RESOLVED",
                details={"knowledge_useful": True, "verification": "requester_confirmed"},
            )
        )

    # 6. Synthetic Resolved Ticket 2 (Rich structured resolution)
    t2 = (
        db.query(Ticket)
        .filter(Ticket.organization_id == org.id, Ticket.ticket_number == "CSD-000002")
        .first()
    )
    if not t2:
        t2 = Ticket(
            organization_id=org.id,
            ticket_number="CSD-000002",
            requester_id=requester.id,
            title="[SYNTHETIC] Single Sign-On session redirect loop in volunteer portal",
            description="[SYNTHETIC] Volunteers trying to sign into the scheduling portal get caught in an infinite authentication loop.",
            status=TicketStatus.RESOLVED,
            priority="NORMAL",
            category="Authentication",
            tags=["sso", "portal", "cookies", "synthetic"],
            queue_id=queues_by_name["IT & Devices"].id,
            assigned_agent_id=agent_user.id,
        )
        db.add(t2)
        db.flush()

        res2 = TicketResolution(
            ticket_id=t2.id,
            organization_id=org.id,
            resolved_by_id=agent_user.id,
            summary="Cleared stale IdP session cookies and updated SAML assertion clock skew tolerance.",
            root_cause="IdP server clock drifted by 4 minutes, causing immediate token expiration on arrival.",
            resolution_steps="1. Synchronized NTP time daemon on authenticating server.\n2. Configured 180s clock skew tolerance in portal config.\n3. Flushed active Redis session cache.",
            verification=VerificationMethod.ADMIN_VERIFIED,
            knowledge_useful=True,
        )
        db.add(res2)

    # 7. Synthetic Open and In Progress tickets
    t3 = (
        db.query(Ticket)
        .filter(Ticket.organization_id == org.id, Ticket.ticket_number == "CSD-000003")
        .first()
    )
    if not t3:
        t3 = Ticket(
            organization_id=org.id,
            ticket_number="CSD-000003",
            requester_id=requester.id,
            title="[SYNTHETIC] Overhead projector bulb flickering in Main Auditorium",
            description="[SYNTHETIC] The projector turns off intermittently every 10 minutes during community town hall.",
            status=TicketStatus.OPEN,
            priority="HIGH",
            category="Facilities",
            tags=["facilities", "auditorium", "projector", "synthetic"],
            queue_id=queues_by_name["Facilities & Rooms"].id,
            assigned_agent_id=agent_user.id,
        )
        db.add(t3)

    t4 = (
        db.query(Ticket)
        .filter(Ticket.organization_id == org.id, Ticket.ticket_number == "CSD-000004")
        .first()
    )
    if not t4:
        t4 = Ticket(
            organization_id=org.id,
            ticket_number="CSD-000004",
            requester_id=requester.id,
            title="[SYNTHETIC] New laptop deployment for youth tutoring program coordinator",
            description="[SYNTHETIC] Need standard productivity bundle and web filter profiles configured for new staff member.",
            status=TicketStatus.IN_PROGRESS,
            priority="NORMAL",
            category="IT",
            tags=["hardware", "onboarding", "synthetic"],
            queue_id=queues_by_name["IT & Devices"].id,
            assigned_agent_id=agent_user.id,
        )
        db.add(t4)

    t5 = (
        db.query(Ticket)
        .filter(Ticket.organization_id == org.id, Ticket.ticket_number == "CSD-000005")
        .first()
    )
    if not t5:
        t5 = Ticket(
            organization_id=org.id,
            ticket_number="CSD-000005",
            requester_id=requester.id,
            title="[SYNTHETIC] Inquiry regarding weekend auditorium air conditioning scheduling",
            description="[SYNTHETIC] Need HVAC scheduled for Saturday afternoon association meeting from 1 PM to 5 PM.",
            status=TicketStatus.NEW,
            priority="LOW",
            category="Facilities",
            tags=["hvac", "facilities", "synthetic"],
            queue_id=queues_by_name["Facilities & Rooms"].id,
            assigned_agent_id=None,
        )
        db.add(t5)

    db.commit()
    print("Database seeding completed successfully.")
    print("Synthetic identities created for local review:")
    print(" - Admin:     admin@metro-community.synthetic")
    print(" - Agent:     agent@metro-community.synthetic")
    print(" - Requester: requester@metro-community.synthetic")
    print(" - Org Slug:  metro-community")


def main():
    parser = argparse.ArgumentParser(prog="csd", description="Community Service Desk CLI")
    subparsers = parser.add_subparsers(dest="command")

    # run command
    run_parser = subparsers.add_parser("run", help="Start the application server")
    run_parser.add_argument("--host", default=None, help="Host to bind to")
    run_parser.add_argument("--port", type=int, default=None, help="Port to listen on")
    run_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # seed command
    subparsers.add_parser("seed", help="Seed database with synthetic demo data")

    # create-tables command
    subparsers.add_parser("create-tables", help="Create all database tables")

    args = parser.parse_args()
    settings = get_settings()

    if args.command == "run":
        host = args.host or settings.host
        port = args.port or settings.port
        print(f"Starting Community Service Desk on http://{host}:{port} ...")
        uvicorn.run(
            "community_service_desk.main:app",
            host=host,
            port=port,
            reload=args.reload,
        )
    elif args.command == "seed":
        create_all_tables()
        db = SessionLocal()
        try:
            seed_database(db)
        finally:
            db.close()
    elif args.command == "create-tables":
        print("Creating all tables...")
        create_all_tables()
        print("Done.")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
