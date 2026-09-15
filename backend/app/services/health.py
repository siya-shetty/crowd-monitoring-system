from app.db.session import database_is_available
def health_payload() -> dict[str, str]: return {"status":"ok", "service":"crowd-monitoring-backend", "database":"available" if database_is_available() else "unavailable"}
