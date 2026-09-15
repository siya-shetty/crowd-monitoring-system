.PHONY: frontend backend cv test
frontend:
	cd frontend && npm run dev
backend:
	cd backend && py -3.13 -m uvicorn app.main:app --reload
cv:
	cd cv-service && py -3.13 -m uvicorn app.main:app --reload --port 8001
test:
	cd frontend && npm test
	cd backend && py -3.13 -m pytest
