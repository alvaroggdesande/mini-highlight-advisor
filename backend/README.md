# Backend (FastAPI)

Install: `.venv/Scripts/python -m pip install -r backend/requirements.txt`
Run:     `.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000`
Test:    `.venv/Scripts/python -m pytest backend/tests -v`

The backend imports the `mini_highlight_advisor` core directly and adapts it to
HTTP. It does not modify `src/`. Streamlit (`streamlit run app.py`) still runs
independently on :8501.
