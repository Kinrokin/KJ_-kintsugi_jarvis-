# Record contracts
JSON schemas describe interchange shape. They do not establish source trust, authentication, full state validity or an approved audience. Runtime validation/state transitions remain authoritative; untrusted strings remain untrusted.

SQLite schemas are defined next to their operational code in household.py and authority.py to avoid drifting duplicate SQL files. Authority, grants and provider receipts have no general household import route. Read the threat model before exposing Python methods to a worker.
