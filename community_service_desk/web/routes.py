"""Server-rendered web UI routes using Jinja2 templates."""

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from community_service_desk.config import get_settings
from community_service_desk.database import get_db
from community_service_desk.models.organization import Organization
from community_service_desk.models.queue import Queue
from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import Membership, User
from community_service_desk.schemas.resolution import ResolutionCreate
from community_service_desk.schemas.search import TicketSearchFilter
from community_service_desk.schemas.ticket import (
    TicketCreate,
)
from community_service_desk.services.attachment_storage_service import AttachmentStorageService
from community_service_desk.services.auth_service import AuthService
from community_service_desk.services.authorization_service import AuthorizationService, Roles
from community_service_desk.services.conversation_service import ConversationService
from community_service_desk.services.knowledge_retrieval_service import KnowledgeRetrievalService
from community_service_desk.services.resolution_service import ResolutionService
from community_service_desk.services.search_service import SearchService
from community_service_desk.services.ticket_lifecycle import TicketLifecycleService
from community_service_desk.services.ticket_service import TicketService

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

web_router = APIRouter(include_in_schema=False)


def get_web_session(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[User | None, Organization | None, str | None]:
    """Helper to resolve current user, organization, and role from web cookies."""
    settings = get_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None, None, None

    payload = AuthService.decode_access_token(token)
    if not payload or "sub" not in payload:
        return None, None, None

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.active:
        return None, None, None

    # Resolve organization
    org_id = request.cookies.get("csd_active_org_id") or payload.get("org_id")
    org = None
    if org_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == org_id, Organization.status == "active")
            .first()
        )

    if not org and user.memberships:
        first_mem = user.memberships[0]
        org = db.query(Organization).filter(Organization.id == first_mem.organization_id).first()

    role = None
    if org:
        mem = AuthorizationService.get_membership(user, org.id)
        if mem:
            role = mem.role

    return user, org, role


@web_router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    user, org, _ = get_web_session(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)


@web_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error, "user": None},
    )


@web_router.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    organization_slug: str = Form(None),
    db: Session = Depends(get_db),
):
    result = AuthService.authenticate_user(
        db, email, password, organization_slug=organization_slug if organization_slug else None
    )
    if not result:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid email, password, or organization. Please try again.",
                "user": None,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user, org_id, role = result
    token = AuthService.create_access_token(
        data={"sub": user.id, "email": user.email, "org_id": org_id, "role": role}
    )

    settings = get_settings()
    redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.access_token_expire_minutes * 60,
    )
    if org_id:
        redirect.set_cookie(
            key="csd_active_org_id",
            value=org_id,
            httponly=True,
            samesite="lax",
            secure=settings.is_production,
            max_age=settings.access_token_expire_minutes * 60,
        )
    return redirect


@web_router.get("/logout")
def logout_get():
    settings = get_settings()
    redirect = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    redirect.delete_cookie(key=settings.cookie_name)
    redirect.delete_cookie(key="csd_active_org_id")
    return redirect


@web_router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    is_staff = role in Roles.STAFF_ROLES
    stats = TicketService.get_dashboard_stats(db, org.id)

    # Scoped tickets list
    req_uid = None if is_staff else user.id
    req_email = None if is_staff else user.email
    filters = TicketSearchFilter(limit=10)
    tickets = SearchService.search_tickets(
        db, org.id, filters, requester_user_id=req_uid, requester_email=req_email
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": is_staff,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "dashboard",
            "stats": stats,
            "tickets": tickets,
        },
    )


@web_router.get("/tickets", response_class=HTMLResponse)
def ticket_list(
    request: Request,
    status: str | None = None,
    priority: str | None = None,
    queue_id: str | None = None,
    unassigned: str | None = None,
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    is_staff = role in Roles.STAFF_ROLES
    req_uid = None if is_staff else user.id
    req_email = None if is_staff else user.email

    filters = TicketSearchFilter(
        status=status,
        priority=priority,
        queue_id=queue_id,
        limit=50,
    )
    tickets = SearchService.search_tickets(
        db, org.id, filters, requester_user_id=req_uid, requester_email=req_email
    )

    if unassigned == "true":
        tickets = [t for t in tickets if t.assigned_agent_id is None]

    queues = db.query(Queue).filter(Queue.organization_id == org.id, Queue.active.is_(True)).all()

    return templates.TemplateResponse(
        "ticket_list.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": is_staff,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "tickets",
            "tickets": tickets,
            "queues": queues,
            "current_status": status,
            "current_priority": priority,
            "current_queue": queue_id,
        },
    )


@web_router.get("/tickets/new", response_class=HTMLResponse)
def ticket_create_page(request: Request, db: Session = Depends(get_db)):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    queues = db.query(Queue).filter(Queue.organization_id == org.id, Queue.active.is_(True)).all()
    return templates.TemplateResponse(
        "ticket_create.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": role in Roles.STAFF_ROLES,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "create_ticket",
            "queues": queues,
        },
    )


@web_router.post("/tickets/new")
def ticket_create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    priority: str = Form("NORMAL"),
    category: str = Form(None),
    tags: str = Form(None),
    queue_id: str = Form(None),
    requester_email: str = Form(None),
    requester_name: str = Form(None),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    is_staff = role in Roles.STAFF_ROLES
    parsed_tags = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else []

    data = TicketCreate(
        title=title,
        description=description,
        priority=priority,
        category=category if category else None,
        tags=parsed_tags,
        queue_id=queue_id if queue_id else None,
        requester_email=requester_email if (is_staff and requester_email) else user.email,
        requester_name=requester_name if (is_staff and requester_name) else user.display_name,
    )

    ticket = TicketService.create_ticket(
        db=db,
        organization_id=org.id,
        data=data,
        actor_user=user if is_staff else None,
        requester_user=user if not is_staff else None,
    )
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@web_router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail_page(
    ticket_id: str,
    request: Request,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)
    is_staff = role in Roles.STAFF_ROLES

    # STRICT SERVER-SIDE INTERNAL NOTE FILTER
    visible_conversations = ConversationService.get_visible_entries(
        ticket.conversation_entries, user, org.id
    )

    # Load staff members for assignment dropdown
    staff_members = []
    if is_staff:
        staff_members = (
            db.query(User)
            .join(Membership)
            .filter(
                Membership.organization_id == org.id,
                Membership.role.in_(Roles.STAFF_ROLES),
                User.active.is_(True),
            )
            .all()
        )

    return templates.TemplateResponse(
        "ticket_detail.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": is_staff,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "tickets",
            "ticket": ticket,
            "conversation_entries": visible_conversations,
            "history_entries": ticket.history_entries if is_staff else [],
            "staff_members": staff_members,
            "message": message,
            "error": error,
        },
    )


@web_router.post("/tickets/{ticket_id}/reply")
def ticket_add_reply(
    ticket_id: str,
    request: Request,
    body: str = Form(...),
    entry_type: str = Form("REQUESTER_VISIBLE_REPLY"),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)

    ConversationService.add_entry(
        db=db,
        ticket=ticket,
        body=body,
        entry_type=entry_type,
        actor=user,
        actor_role=role,
    )
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@web_router.post("/tickets/{ticket_id}/status")
def ticket_update_status(
    ticket_id: str,
    request: Request,
    status_val: str = Form(..., alias="status"),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    TicketLifecycleService.transition_status(
        db=db, ticket=ticket, new_status=status_val, actor=user
    )
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@web_router.post("/tickets/{ticket_id}/assign")
def ticket_update_assignment(
    ticket_id: str,
    request: Request,
    assigned_agent_id: str = Form(None),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    agent_id = assigned_agent_id if assigned_agent_id else None
    TicketService.assign_ticket(db=db, ticket=ticket, assigned_agent_id=agent_id, actor=user)
    return RedirectResponse(url=f"/tickets/{ticket.id}", status_code=status.HTTP_303_SEE_OTHER)


@web_router.get("/tickets/{ticket_id}/resolve", response_class=HTMLResponse)
def ticket_resolve_page(ticket_id: str, request: Request, db: Session = Depends(get_db)):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)
    return templates.TemplateResponse(
        "ticket_resolve.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": True,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "tickets",
            "ticket": ticket,
        },
    )


@web_router.post("/tickets/{ticket_id}/resolve")
def ticket_resolve_post(
    ticket_id: str,
    request: Request,
    summary: str = Form(...),
    root_cause: str = Form(None),
    resolution_steps: str = Form(...),
    verification: str = Form("admin_verified"),
    knowledge_useful: bool = Form(False),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_modification(user, ticket)

    data = ResolutionCreate(
        summary=summary,
        root_cause=root_cause if root_cause else None,
        resolution_steps=resolution_steps,
        verification=verification,
        knowledge_useful=knowledge_useful,
    )
    ResolutionService.record_resolution(db=db, ticket=ticket, data=data, actor=user)
    return RedirectResponse(
        url=f"/tickets/{ticket.id}?message=Ticket+resolved+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.post("/tickets/{ticket_id}/attachments")
async def ticket_upload_attachment(
    ticket_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    ticket = (
        db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.organization_id == org.id).first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")

    AuthorizationService.assert_ticket_access(user, ticket)
    await AttachmentStorageService.save_attachment(db=db, ticket=ticket, file=file, actor=user)
    return RedirectResponse(
        url=f"/tickets/{ticket.id}?message=Attachment+uploaded+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    is_staff = role in Roles.STAFF_ROLES
    req_uid = None if is_staff else user.id
    req_email = None if is_staff else user.email

    searched = bool(q or status or priority or category or tag)
    results = []

    if searched:
        filters = TicketSearchFilter(
            query=q,
            status=status,
            priority=priority,
            category=category,
            tag=tag,
            limit=50,
        )
        results = SearchService.search_tickets(
            db, org.id, filters, requester_user_id=req_uid, requester_email=req_email
        )

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": is_staff,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "search",
            "searched": searched,
            "query_str": q,
            "status": status,
            "priority": priority,
            "category": category,
            "tag": tag,
            "results": results,
        },
    )


@web_router.get("/knowledge", response_class=HTMLResponse)
def knowledge_page(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    AuthorizationService.require_agent(user, org.id)

    searched = bool(q)
    evidence = []
    if searched:
        tags = [tag.strip()] if tag else []
        evidence = KnowledgeRetrievalService.retrieve_evidence(
            db=db,
            organization_id=org.id,
            query=q or "",
            category=category,
            tags=tags,
            limit=10,
        )

    return templates.TemplateResponse(
        "knowledge.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": True,
            "is_admin": role == Roles.ORGANIZATION_ADMIN,
            "active_page": "knowledge",
            "searched": searched,
            "query_str": q,
            "category": category,
            "tag": tag,
            "evidence": evidence,
        },
    )


@web_router.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    AuthorizationService.require_admin(user, org.id)

    members = db.query(Membership).filter(Membership.organization_id == org.id).all()
    queues = (
        db.query(Queue).filter(Queue.organization_id == org.id).order_by(Queue.name.asc()).all()
    )

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "role": role,
            "is_staff": True,
            "is_admin": True,
            "active_page": "admin",
            "members": members,
            "queues": queues,
            "message": message,
            "error": error,
        },
    )


@web_router.post("/admin/members")
def admin_add_member(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    role_val: str = Form("agent", alias="role"),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    AuthorizationService.require_admin(user, org.id)

    target_user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not target_user:
        target_user = User(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=AuthService.hash_password(password),
            active=True,
        )
        db.add(target_user)
        db.flush()

    existing_mem = (
        db.query(Membership)
        .filter(Membership.organization_id == org.id, Membership.user_id == target_user.id)
        .first()
    )
    if existing_mem:
        return RedirectResponse(
            url="/admin?error=User+is+already+a+member+of+this+organization",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    mem = Membership(
        organization_id=org.id,
        user_id=target_user.id,
        role=role_val,
    )
    db.add(mem)
    db.commit()
    return RedirectResponse(
        url="/admin?message=Team+member+added+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@web_router.post("/admin/queues")
def admin_add_queue(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db),
):
    user, org, role = get_web_session(request, db)
    if not user or not org:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    AuthorizationService.require_admin(user, org.id)

    existing = (
        db.query(Queue).filter(Queue.organization_id == org.id, Queue.name == name.strip()).first()
    )
    if existing:
        return RedirectResponse(
            url="/admin?error=Queue+name+already+exists",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    queue = Queue(
        organization_id=org.id,
        name=name.strip(),
        description=description.strip() if description else None,
        active=True,
    )
    db.add(queue)
    db.commit()
    return RedirectResponse(
        url="/admin?message=Queue+created+successfully",
        status_code=status.HTTP_303_SEE_OTHER,
    )
