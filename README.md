# PropFlow

A private dashboard for a small rental portfolio. It tracks rent and Section 8 payments, expenses filed by Schedule E line, tenants and leases, maintenance, and contacts. At tax time it produces a per-property Schedule E summary and a zip for your CPA.

It runs on your own VPS and is reachable only from your devices over Tailscale. Nothing is public.

## What's in it

| Page | What you do there |
|---|---|
| **Home** | See this month's rent collected vs expected, who's late, year-to-date net per property, leases ending, open maintenance. |
| **Rent roll** | Month by month: every lease, what was due, what came in, and a Paid / Partial / Late stamp. One tap records the missing payment. |
| **Payments** | Money in: rent, Section 8 HAP, late fees, other income, security deposits (held, not income), deposits kept (income). |
| **Expenses** | Money out, each tagged with a Schedule E category. Snap a receipt from your phone. A mortgage splitter turns one payment into interest (deductible), principal and escrow (tracked). |
| **Taxes** | Schedule E lines 3–21, one column per property. Shared costs (CPA, umbrella policy) split evenly or shown separately. Depreciation estimate. Download CSV or a CPA zip with every receipt. |
| **Properties / Tenants** | Units, purchase details, leases with Section 8 split, balances, move-outs, renewals, documents. |
| **Maintenance / Contacts** | A simple work log linked to bills, and your vendors, lender and housing authority. |
| **Import** | Upload a CSV of properties, tenants, payments or expenses. Preview, see errors and duplicates, then add. |

## Put it on the VPS (one time, about 5 minutes)

You need: an Ubuntu/Debian VPS with Tailscale running (`sudo tailscale up`), and Tailscale on your phone.

```bash
# On the VPS, as your normal user
git clone https://github.com/jarviss12a-prog/propflow.git ~/propflow
cd ~/propflow
bash deploy/setup.sh
```

The script:

1. installs Python packages into `.venv`
2. writes `.env` with a random secret key and a free port (8050 unless something already uses it)
3. asks you to choose your PropFlow password
4. installs a `propflow` systemd service that listens on **127.0.0.1 only**
5. adds a nightly backup at 3:15 am
6. runs `tailscale serve` so the app is at `https://<your-vps>.<tailnet>.ts.net` (port 443, or 8443 if another app already uses 443)

Open that URL on your phone with Tailscale on, sign in, and in Safari tap **Share → Add to Home Screen**.

If `tailscale serve` fails, it's usually because HTTPS certificates are off for your tailnet. Turn them on in the Tailscale admin console under **DNS → HTTPS Certificates** and run the script again, or follow the plain-IP fallback the script prints.

### If the repo is private

The VPS needs permission to pull. Either run `gh auth login` on the VPS once, or add a read-only deploy key (GitHub → repo → Settings → Deploy keys) and clone with `git@github.com:jarviss12a-prog/propflow.git`.

## Updating

```bash
cd ~/propflow && bash deploy/update.sh
```

This backs up first, pulls, reinstalls packages and restarts. Your `data/` folder and `.env` are never touched by git.

## Getting your numbers in

- **A few at a time:** use **Record** (top right) on your phone.
- **A whole year at once:** go to **Import**, pick the type, download the template, fill it in (or export your existing sheet as CSV), upload, check the preview, and add. Order matters: properties, then tenants, then payments and expenses.
- **From the command line on the VPS:** `.venv/bin/python manage.py import payments ~/jan-payments.csv`

Importing the same file twice is safe. Rows that match something already in PropFlow are flagged and skipped unless you tick the box to include them.

## Backups

Every night `data/backups/propflow-YYYY-MM-DD_HHMM.tar.gz` holds the database and all receipts. The last 30 are kept. Those backups live on the same VPS, so copy them somewhere else now and then, for example from your computer:

```bash
scp 'you@your-vps:~/propflow/data/backups/*.tar.gz' ~/propflow-backups/
```

To restore: stop the service, extract the archive into `data/`, start the service.

## Commands

```bash
.venv/bin/python manage.py set-password      # reset your password
.venv/bin/python manage.py import KIND FILE  # properties | tenants | payments | expenses
.venv/bin/python manage.py backup            # backup now
.venv/bin/python manage.py check             # row counts
sudo systemctl status propflow               # is it running?
sudo journalctl -u propflow -n 100           # logs
```

## How the numbers work

- Money is stored as whole cents, so totals never drift.
- **Rent roll:** a lease expects its full rent every month from its start (or the "Track rent from" month) until the move-out date. A lease end date alone doesn't stop rent, because tenants often stay on month to month.
- **Section 8:** a lease has a total rent and a HAP amount. The rent roll shows the tenant's part and the housing authority's part separately and marks the month paid when both are in.
- **Balance:** opening balance + rent for each month whose due day has passed − rent and HAP received for those months.
- **Schedule E line 3** = rent + HAP + late fees + other income + deposits kept. Security deposits received are excluded and shown as a liability.
- **Depreciation** is an estimate: straight-line over 27.5 years on purchase price minus land value, mid-month convention. It ignores improvements. Your CPA's schedule is the real one.

PropFlow organizes records; it isn't tax advice.

## Developing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py demo          # sample data in ./data (only if empty)
.venv/bin/python wsgi.py                 # http://127.0.0.1:8050
.venv/bin/pytest -q
```

Flask + SQLite + server-rendered Jinja templates, one CSS file, a few lines of optional JavaScript. No build step.
