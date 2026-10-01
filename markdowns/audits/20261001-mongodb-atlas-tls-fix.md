# Security & Correctness Audit

## Review of Changes
- Removed explicit `tlsCAFile` parameter relying on `certifi` from the PyMongo `MongoClient` connection in `store.py`.

## Potential Flaws & Vulnerabilities
- **Severity: None.** Removing `tlsCAFile` makes the application rely on the operating system's native CA certificate trust store (e.g., `/etc/ssl/certs/ca-certificates.crt` on Linux/Render). This is standard practice and often more secure/up-to-date than bundled python packages like `certifi`. The connection remains fully encrypted with TLS (enforced by the `mongodb+srv://` scheme).
- The root cause of the error is an external security mechanism (MongoDB Atlas IP Whitelist) blocking the connection, which cannot be bypassed via code. The user must manually configure this.

## Mitigations
- Informed the user that they must allow `0.0.0.0/0` in Atlas to support Render's dynamic IPs. Since MongoDB Atlas requires strong authentication (username/password in the URI), allowing connections from anywhere is common practice for PaaS deployments and relies on credential security.

## Tests Not Run
- Not tested against the live Atlas cluster since we don't have access to the user's Atlas credentials or dashboard to verify the IP whitelist.
