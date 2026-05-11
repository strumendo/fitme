# fitme

Personal app to track fitness evolution using Garmin Connect data, training routine and food log.

## Quickstart

```bash
# 1. Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies (creates .venv automatically)
uv sync

# 3. Configure credentials
cp .env.example .env
$EDITOR .env  # fill GARMIN_EMAIL and GARMIN_PASSWORD

# 4. One-off Garmin login (handles MFA, caches tokens to ~/.garminconnect)
uv run python -m fitme.login

# 5. Run the dashboard
uv run streamlit run app.py
```

After step 4 the OAuth tokens are cached, so the dashboard starts without
prompting for password or MFA until the refresh token expires.

## Stack

Python 3.12 · uv · Streamlit · [garminconnect](https://github.com/cyberjunky/python-garminconnect) · python-dotenv · pandas
