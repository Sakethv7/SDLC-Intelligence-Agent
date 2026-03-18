# Merge Request Security Policy

## High-Risk Change Patterns (require security review)
- Changes to authentication or session management code
- New external API integrations or HTTP clients
- Database schema changes involving PII
- New file upload or download functionality
- Changes to permission/role logic
- New environment variable handling
- Modifications to CI/CD pipeline configuration
- New third-party dependencies
- Changes to cryptographic functions or token generation

## Automatic Block Criteria (MR must not merge)
- Any hardcoded secret, password, or API key detected
- SSL/TLS verification disabled (`verify=False`, `NODE_TLS_REJECT_UNAUTHORIZED=0`)
- Use of `eval()` or `exec()` with any non-literal input
- Raw SQL string interpolation with user-supplied variables
- Dependencies with CVSS score >= 9.0 (Critical)
- Private keys or certificates in diff

## Medium Risk — Requires Comment
- New `subprocess` or shell command execution
- Broad file system access patterns
- Disabling of security linters or scanners in CI
- Relaxing of CORS policy
- New admin-level API endpoints without rate limiting

## Low Risk — Best Practice Suggestions
- Missing input length validation
- Overly broad exception catching (`except Exception`)
- Debug logging left in production code paths
- Missing timeout on network calls
- Unused imports that could indicate leftover debug code
