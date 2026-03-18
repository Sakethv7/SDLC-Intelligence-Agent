# Secure Coding Standards

## Secrets Management
- All secrets MUST be loaded from environment variables or a secrets manager
- Prohibited patterns in code: hardcoded passwords, tokens starting with sk-, glpat-, ghp_, AWS keys
- Pre-commit hooks must include secret scanning (e.g. detect-secrets, truffleHog)
- If a secret is accidentally committed, rotate it immediately and purge git history

## Authentication & Authorization
- Every API endpoint must have explicit authentication check
- Use established auth libraries — never roll your own crypto
- OAuth tokens must have the minimum required scopes
- Service accounts must use short-lived tokens, not long-lived PATs

## Input Validation
- Validate all inputs at the API boundary
- Use strict type checking — reject unexpected fields
- Limit input length to prevent DoS via large payloads
- Sanitize file names and paths to prevent directory traversal

## Dependency Management
- No new direct dependencies without security review
- Indirect dependencies must be locked in a lockfile
- Dependencies must be reviewed monthly for CVEs
- Use SBOM (Software Bill of Materials) for all production releases

## Code Review Security Checklist
- [ ] No hardcoded secrets or credentials
- [ ] All user inputs validated and sanitized
- [ ] SQL/NoSQL queries use parameterized form
- [ ] Error messages do not expose stack traces or internal details
- [ ] New endpoints have authentication and authorization
- [ ] Sensitive data is not logged
- [ ] Dependencies are pinned and audited
- [ ] No use of eval(), exec(), or dynamic code execution with user input

## File & Path Security
- Never use user input directly in file paths
- Use os.path.basename() and validate against allowed directories
- Set restrictive file permissions (600 for secrets, 644 for public)

## Network Security
- All outbound HTTP must use HTTPS
- Validate TLS certificates — never disable SSL verification
- Implement timeouts on all network calls (max 30s)

## Logging Policy
- Log: authentication events, authorization failures, input validation errors, system errors
- Never log: passwords, tokens, credit card numbers, SSNs, health data
- Structured logging (JSON) required for all production services
