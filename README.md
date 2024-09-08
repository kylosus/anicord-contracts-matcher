# Automatic Matcher for Anicord Contracts

This is how you got that weird anime assigned to you

---

The script uses a simple heuristic to "fairly" distribute
the pool among all users while avoiding matching shows
they have seen.

Queries made to AniList will be retried on 429
forever using the minimum wait times returned by their system until either a success or
an error. Successful requests are cached in `cache/` for 1
year and the script can safely be re-run.

## Usage:

- `pip install .`
- Put the pool of anilist links in `pool.txt`
  - After each line place a space, pipe, a second space, and then either `S` or `T` to indicate "Staff" (some seasons "Veteran") or "Trash" specials respectively
- Put the pool of users in `usernames.txt`
  - After each line place a space, pipe, a second space, and then either `S`, `T`, or `B` to indicate "Staff" (some seasons "Veteran"), "Trash", or "Both" specials respectively
- Run `main.py`

### Spring 2024

`data/pool.txt` in the repo contains staff picks for the season

`data/usernames.txt` has been redacted for privacy reasons.

Both of these contain examples of the proper formatting.
