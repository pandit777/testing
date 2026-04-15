# testing

## Local setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create env file:
   ```bash
   cp .env.example .env
   ```
3. Update at least:
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
4. Run app:
   ```bash
   python main.py
   ```

## Vercel notes

- Add the same variables from `.env.example` in **Vercel Project → Settings → Environment Variables**.
- For persistent users/database across server restarts, set `DATABASE_PATH` to a persistent storage location (or migrate to managed DB).
