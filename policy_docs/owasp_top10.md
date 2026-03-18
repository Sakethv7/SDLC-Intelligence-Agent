# OWASP Top 10 Security Policy

## A01 - Broken Access Control
- Enforce least privilege on all endpoints
- Deny access by default; explicitly allow
- Never expose directory listings
- Log and alert on access control failures
- Invalidate JWT tokens server-side on logout

## A02 - Cryptographic Failures
- Never store passwords in plain text; use bcrypt/argon2
- Encrypt sensitive data at rest and in transit (TLS 1.2+)
- Never hardcode secrets, API keys, or credentials in source code
- Use secrets manager (Vault, AWS Secrets Manager) for all credentials
- Never commit .env files or private keys to version control

## A03 - Injection
- Use parameterized queries / prepared statements for all DB access
- Never interpolate user input directly into SQL, shell commands, or LDAP queries
- Validate and sanitize all user-supplied input
- Use allowlists, not denylists, for input validation

## A04 - Insecure Design
- Threat model all new features before implementation
- Apply defense in depth — no single point of security failure
- Rate-limit all authentication endpoints

## A05 - Security Misconfiguration
- Remove default credentials and unused features
- Keep all dependencies up to date and scan with SCA tools
- Disable debug mode and stack traces in production
- Set secure HTTP headers: CSP, HSTS, X-Frame-Options

## A06 - Vulnerable and Outdated Components
- Pin all dependency versions; avoid wildcard ranges
- Run `pip audit` / `npm audit` in CI on every MR
- Never use components with known CVEs above CVSS 7.0

## A07 - Identification and Authentication Failures
- Enforce MFA for all admin and production access
- Implement account lockout after repeated failures
- Use secure, random session tokens (min 128 bits)
- Expire sessions after inactivity

## A08 - Software and Data Integrity Failures
- Verify integrity of all third-party libraries (checksums, signatures)
- Use signed commits in Git
- Never deserialize untrusted data without validation

## A09 - Security Logging and Monitoring Failures
- Log all authentication events, access control failures, and input validation errors
- Do not log sensitive data (passwords, tokens, PII)
- Alert on anomalous patterns within 1 minute

## A10 - Server-Side Request Forgery (SSRF)
- Validate and sanitize all URLs supplied by users
- Use allowlists for permitted domains in outbound requests
- Block requests to internal/private IP ranges from user-controlled URLs
