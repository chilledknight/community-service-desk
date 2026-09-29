# Community Service Desk - Security Architecture & Policy

**Version:** 0.1.1  
**License:** AGPL-3.0-only  

---

## 1. Security Overview

Community Service Desk is engineered with a defense-in-depth posture appropriate for public community organizations, schools, non-profits, and small businesses handling sensitive internal support conversations.

---

## 2. Core Security Boundaries

### 2.1 Multi-Tenant Organization Boundary
- Every tenant organization exists within an isolated logical boundary.
- **Rule:** A user associated with Organization A must never view, list, modify, or infer the existence of tickets, requesters, queues, or resolutions belonging to Organization B.
- **Enforcement:** Enforced at the database query layer (`organization_id == current_org.id`). Attempting to access an ID from another tenant produces an immediate `404 Not Found`.

### 2.2 The Internal Note Boundary
Support teams require private channels for handoffs, diagnostic musings, and administrative commentary.
- **Rule:** A ticket requester must **NEVER** see an internal note.
- **Enforcement:**
  1. Internal notes are saved with `entry_type = 'INTERNAL_NOTE'`.
  2. The server-side conversation service completely filters out `INTERNAL_NOTE` entries before serializing data for non-staff users.
  3. Requesters attempting to POST `entry_type: 'INTERNAL_NOTE'` receive an immediate `403 Forbidden`.
  4. In the agent interface, internal notes feature unmistakable visual warnings (amber background, dashed borders, and clear "INTERNAL NOTE • STAFF ONLY" badges).

### 2.3 Requester Privacy Boundary
- Requesters can only access their own tickets (matching their registered `user_id` or verified `email`).
- Requesters cannot access other community members' tickets or private organizational audit history.

---

## 3. Authentication & Password Security

- **Hashing Algorithm:** Key derivation utilizes Python standard library `hashlib.scrypt` with a 16-byte cryptographic salt (`secrets.token_bytes(16)`), CPU/memory cost parameter $N=16384$, block size $r=8$, parallelization $p=1$, and key length 64 bytes.
- **Timing Attack Mitigation:** Verification utilizes constant-time comparison via `hmac.compare_digest`.
- **Sessions & Tokens:** Signed JWT access tokens with configurable expiration (default 8 hours). Tokens are transmitted via `Authorization: Bearer <token>` or encrypted, HttpOnly, SameSite=Lax browser cookies.
- **External Auth Ready:** The authentication layer separates user identity from ticket authorization. External OIDC/OAuth providers (e.g. Google, Microsoft 365, Keycloak) can be added without altering ticket business logic.

---

## 4. File Storage & Attachment Safety

- **Path Traversal Prevention:** Uploaded filenames are sanitized and files are stored on disk using non-sequential UUID4 hex identifiers (`uuid.uuid4().hex + extension`).
- **File Type Restrictions:** Dangerous executable and script file extensions (`.exe`, `.bat`, `.cmd`, `.sh`, `.vbs`, `.ps1`, `.msi`, `.dll`, `.scr`, `.com`) are strictly rejected.
- **Size Limits:** Enforced maximum upload ceiling (default 10 MB).
- **Authorized Download:** Attachment downloads require prior tenant and ticket access verification before byte streaming occurs.
- **Production Hardening Note:** For high-volume production deployments, integrating an automated anti-malware scanner (e.g., ClamAV) and offloading to private S3/GCS buckets with signed URLs is recommended.

---

## 5. Input Validation & Output Escaping

- All API inputs are strictly typed and validated using Pydantic v2 schemas.
- Server-rendered HTML utilizes Jinja2 autoescaping by default to prevent Cross-Site Scripting (XSS).
- SQL injection is prevented by utilizing SQLAlchemy parameterized queries.
