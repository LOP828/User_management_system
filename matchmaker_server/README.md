# Matchmaker Server

## Scope

This directory contains the backend scaffold for the MVP.

Current implemented scope:
- `S00_base_scaffold`
- `0001_foundation_schema`
- `0002_bootstrap_seed`
- `0003_user_core`

Not implemented yet:
- `S01_auth_staff_config` and any business logic after it

## Local setup

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and update local values.
3. Run migrations after dependencies are installed:

```bash
python manage.py migrate
```

## Notes

- `staff` is the Django `AUTH_USER_MODEL`.
- Passwords must use Django's standard password hashing flow.
- Default admin accounts are not created by migrations.
- Admin initialization command will be implemented in the `S01_auth_staff_config` batch.
- `0002_bootstrap_seed` only seeds currently confirmed `reason_enum` defaults for `pause`, `overdue`, and `risk`.
