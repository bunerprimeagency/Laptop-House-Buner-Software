# Laptop House Buner — Streamlit version

## Deploy on Streamlit Community Cloud

1. Create/sign in to GitHub.
2. Create a **private** repository (recommended because the app is for your shop).
3. Upload `streamlit_app.py`, `requirements.txt`, and this README.
4. In Streamlit Community Cloud choose **New app**, select the repository, and set Main file path to `streamlit_app.py`.
5. Deploy.
6. On first run, default logins are:
   - Owner username: `owner`
   - Owner password: `ChangeOwnerPass!2026`
   - Employee username: `employee`
   - Employee password: `ChangeStaffPass!2026`
7. Change these default passwords before real business use. You can set secrets/environment variables `LHB_OWNER_PASSWORD` and `LHB_STAFF_PASSWORD` before first database initialization.

## Import existing data

In the app, log in as owner -> **Database Backup** -> upload your current `laptop_house.db` -> download a backup of the current online database first -> tick the confirmation -> Restore.

## Important data warning

This app uses SQLite for compatibility with your existing local app. Streamlit Community Cloud's local filesystem should not be treated as durable business storage; app restarts/redeployments can risk data loss. Do not use it for live sales until a persistent database has been configured. Also, this package does **not** automatically sync with the Windows laptop's local database. True multi-device online syncing requires a persistent cloud database and connecting both the local app and hosted app to it.

## Local run

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Security

The login is a basic app-level login, not enterprise authentication. Keep the repository private, change default passwords, and do not publish customer data or the `.db` file in a public GitHub repository.
