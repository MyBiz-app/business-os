# Rotating the platform encryption key

`API_SECRETS_KEY` is a Fernet key. It seals the businesses' provider secrets and social tokens,
ID numbers (`person_identities`), employees' bank accounts and Form 101 answers
(`employment_profiles`, `form101_forms`), pending social page choices, and sensitive files such as
payslips (`business_files` with `encrypted`). Signed links are signed with a key derived from it.

Rotate **once a year**, **at once if it may have leaked** (a laptop, a log, a departing person), and
whenever someone who knew it leaves. Nothing needs to stop: while two keys are listed, old and new
values both work.

## How it works

- `API_SECRETS_KEYS` is a comma-separated list, **newest first**. The first key encrypts; every key
  decrypts (`MultiFernet`). It replaces `API_SECRETS_KEY`; while only the old single variable is
  set, nothing changes.
- `python -m app.jobs rotate-secrets` re-encrypts every stored value with the first key. Without
  `--apply` it only counts the values still on an older key. A value the first key already opens is
  left alone, so a run can be repeated or stopped.
- Signed links (10 minutes long) are signed with the first key and accepted from any listed key.

## Steps

Use a terminal that is not logged, never paste a key into a chat, an issue or a commit. Production and
staging each have their own key.

1. **Generate** the new key:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   and store it in the provider secret store (Render, and the GitHub environment secrets for the
   scheduled jobs). Keep the old key there too until step 7.
2. **Pin the ID-number hash** (only the first time, see below): set `API_ID_HASH_KEY` to the **old**
   key in every place the API and the jobs run.
3. **Add the new key in front**: set `API_SECRETS_KEYS=<new>,<old>` in every place that has
   `API_SECRETS_KEY` (the API service, the cron jobs, the GitHub jobs workflows). Deploy.
   Check that the API starts, a business's provider settings still open, and a payslip downloads.
4. **Count** what is on the old key:
   `python -m app.jobs rotate-secrets` (a report per column: `stale` is what remains).
5. **Re-encrypt**: `python -m app.jobs rotate-secrets --apply`. It fails, and changes nothing more,
   on a value no listed key opens: stop and find the key that does (an even older one) before going on.
6. **Verify**: run step 4 again; every `stale` is 0.
7. **Retire the old key**: set `API_SECRETS_KEYS=<new>` (and remove `API_SECRETS_KEY`), deploy, and
   delete the old key from the secret stores. Keep a sealed copy of the old key only as long as a
   database backup older than step 5 might still need to be restored (see
   `docs/deploy/restore-runbook.md`): such a backup needs the old key.

If the API cannot start after step 3 it is a typo in the list: fix the variable; no data was changed
yet. If something is wrong after step 5, the old key is still listed, so nothing is lost.

## What does not rotate by itself

- **The ID-number hash** (`person_identities.id_hash`, used to spot a duplicate ID number) is an
  HMAC. A new key would give different hashes, so it is keyed by `API_ID_HASH_KEY`, or while that is
  unset by the **last** (oldest) key in the list. So: set `API_ID_HASH_KEY` to the key that was
  current when the hashes were made (step 2) before the old key leaves the list, and leave it
  unchanged afterwards. Changing the hash key itself means recomputing every hash from the decrypted
  numbers: not built, and not needed unless that key leaked (then the hashes of ID numbers could be
  guessed; plan a one-off script with the owner).
- **Files in the object store** are re-encrypted by `rotate-secrets` too (it reads and writes them
  through the business's storage provider); a storage outage makes the run fail, and it is safe to run again.
- **Backups** keep whatever key sealed them (see step 7).

## Test

`apps/api/tests/test_key_rotation.py`: encrypting with an old key, adding a new one, rotating, and
decrypting with the new one alone; signed links; the ID hash; sealed files. The tests use generated
keys only.
