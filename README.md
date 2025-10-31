# EDI Translator/Validator (FastAPI + React)

A minimal, working project to upload an X12 EDI file, auto-detect the transaction set (850/810 supported), parse segments to JSON, and run basic validation rules. Great as a portfolio project for EDI Coordinator roles.

## Quick start

### 1) Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open the printed local URL (usually http://localhost:5173). Upload one of the sample files:
- `backend/samples/850.edi`
- `backend/samples/810.edi`

## What it does
- Infers X12 delimiters (segment `~`, elements `*`, components `:`)
- Detects transaction type via `ST*<setId>`
- Validates envelopes (ISA/GS/GE/IEA), ST/SE counts
- Adds basic rules for 850 (BEG present + ordering) and 810 (BIG present)
- Returns structured JSON the UI renders (segments + validation messages)

## Notes
- CORS is enabled to allow the React dev server to call the API.
- You can deploy the backend using the provided Dockerfile.
- Extend validation by adding functions in `VALIDATORS`.
