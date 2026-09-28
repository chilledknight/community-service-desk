"""Authorization policies and multi-tenant isolation enforcement."""

from fastapi import HTTPException, status

from community_service_desk.models.ticket import Ticket
from community_service_desk.models.user import Membership, User


class Roles:
    ORGANIZATION_ADMIN = "organization_admin"
    AGENT = "agent"
    REQUESTER = "requester"

    STAFF_ROLES = {ORGANIZATION_ADMIN, AGENT}


class AuthorizationService:
    """Enforces server-side permissions and tenant boundary checks."""

    @staticmethod
    def get_membership(user: User, organization_id: str) -> Membership | None:
        """Find active membership for a user in a specific organization."""
        for m in user.memberships:
            if m.organization_id == organization_id:
                return m
        return None

    @classmethod
    def require_organization_member(cls, user: User, organization_id: str) -> Membership:
        """Ensure the user is a member of the organization, else raise 403."""
        membership = cls.get_membership(user, organization_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have access to this organization.",
            )
        return membership

    @classmethod
    def require_agent(cls, user: User, organization_id: str) -> Membership:
        """Ensure the user is an agent or organization_admin, else raise 403."""
        membership = cls.require_organization_member(user, organization_id)
        if membership.role not in Roles.STAFF_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Agent or Administrator privileges required.",
            )
        return membership

    @classmethod
    def require_admin(cls, user: User, organization_id: str) -> Membership:
        """Ensure the user is an organization_admin, else raise 403."""
        membership = cls.require_organization_member(user, organization_id)
        if membership.role != Roles.ORGANIZATION_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Administrator privileges required.",
            )
        return membership

    @classmethod
    def can_view_ticket(cls, user: User, ticket: Ticket) -> bool:
        """Check if user can view a specific ticket."""
        membership = cls.get_membership(user, ticket.organization_id)
        if not membership:
            return False

        # Staff can view all tickets in their organization
        if membership.role in Roles.STAFF_ROLES:
            return True

        # Requesters can only view their own tickets
        if ticket.requester:
            if ticket.requester.user_id == user.id:
                return True
            if ticket.requester.email.lower() == user.email.lower():
                return True

        return False

    @classmethod
    def assert_ticket_access(cls, user: User, ticket: Ticket) -> Membership:
        """Assert user has read access to ticket; raise 403 or 404 on violation."""
        membership = cls.get_membership(user, ticket.organization_id)
        if not membership:
            # Conceal existence across tenants
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found.",
            )

        if not cls.can_view_ticket(user, ticket):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to view this ticket.",
            )
        return membership

    @classmethod
    def assert_ticket_modification(cls, user: User, ticket: Ticket) -> Membership:
        """Assert user is staff with write permissions on the ticket."""
        membership = cls.require_agent(user, ticket.organization_id)
        return membership

    @classmethod
    def can_view_internal_notes(cls, user: User, organization_id: str) -> bool:
        """Determine if user is authorized to view internal notes.

        CRITICAL PRIVACY BOUNDARY:
        Only agents and administrators can view internal notes.
        Requesters NEVER see internal notes under any circumstances.
        """
        membership = cls.get_membership(user, organization_id)
        return bool(membership and membership.role in Roles.STAFF_ROLES)

    @classmethod
    def can_view_audit_history(cls, user: User, organization_id: str) -> bool:
        """Determine if user is authorized to view ticket audit event history."""
        membership = cls.get_membership(user, organization_id)
        return bool(membership and membership.role in Roles.STAFF_ROLES)
