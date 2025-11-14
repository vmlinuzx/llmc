# Example Architect Spec - User Authentication Feature

### GOAL
Add JWT-based user authentication with 24h token expiry

### FILES
- src/auth.py [CREATE] - JWT validation middleware
- src/models.py [MODIFY] - add User.last_login field
- config/secrets.env [CREATE] - JWT_SECRET, JWT_EXPIRY
- tests/test_auth.py [CREATE] - auth unit tests
- docs/auth_api.md [CREATE] - API authentication guide

### FUNCS
- auth.verify_token(token: str) → User | None - validate JWT
- auth.create_token(user: User) → str - generate signed token
- auth.hash_password(password: str) → str - bcrypt hash
- models.User.update_last_login() → None - timestamp login
- models.User.verify_password(password: str) → bool - check hash

### POLICY
- Tokens expire in 24h (JWT_EXPIRY=86400)
- SECRET must be ≥32 chars, env-only (never commit)
- Failed auth → 401, rate limit 5/min/IP
- Passwords must be ≥8 chars with mixed case + numbers
- Hash algorithm: bcrypt with cost=12

### TESTS
- Valid token → User object returned
- Expired token → None, logs warning
- Malformed token → None, no crash
- Missing SECRET → startup error
- Password hash → verify roundtrip works
- Rate limiting → 6th attempt blocked

### RUNBOOK
1. Generate SECRET: `openssl rand -hex 32 > config/secrets.env`
2. Install deps: `pip install pyjwt[crypto] bcrypt`
3. Run migrations: `python manage.py migrate`
4. Test: `pytest tests/test_auth.py -v`
5. Deploy: restart server to load new SECRET
6. Monitor: track `auth_failures` metric for attacks

### RULES
- NO prose
- NO redundancy
- Use symbols/paths
- ≤900 tokens
