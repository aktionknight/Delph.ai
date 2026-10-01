# Scope
Address the MongoDB connection error `TLSV1_ALERT_INTERNAL_ERROR` during backend deployment on Render.

# Implemented Changes
- Removed `tlsCAFile=certifi.where()` and the `certifi` import from `MongoClient` initialization in `apps/api/app/services/store.py`.

# Architectural Decisions
- The primary cause of `TLSV1_ALERT_INTERNAL_ERROR` on MongoDB Atlas is connecting from an IP address not whitelisted in the Atlas Network Access panel. Atlas terminates the connection during the TLS handshake for unauthorized IPs, presenting as an SSL/TLS alert rather than a standard connection timeout.
- Additionally, forcing `tlsCAFile=certifi.where()` can sometimes cause TLS negotiation issues on modern Linux environments (like Render's Python 3.14 image) if `certifi`'s bundle conflicts with the system's native OpenSSL CA trust store. Removing it allows PyMongo to use the robust system default trust store natively.

# Next Steps
- The user must explicitly add `0.0.0.0/0` (Allow Access from Anywhere) to their MongoDB Atlas Network Access IP Whitelist, as Render uses dynamic outbound IPs that cannot be statically whitelisted.
