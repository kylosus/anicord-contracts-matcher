# Automatic Matcher for Anicord Contracts
This is how you got that weird anime assigned to you

---

The script uses a simple heuristic to "fairly" distribute
the pool among all users while avoiding matching shows
they have seen.

Queries made to AniList will be retried on 429
forever in doubled increments until either a success or
an error. Successful requests are cached in `cache/` for 1
year and the script can safely be re-run.

### Usage:
- `pip install .`
- Put the pool of anilist links in `pool.txt`
- Put the pool of users in `usernames.txt`
- Run `main.py`

### Spring 2024
`data/pool.txt` in the repo contains staff picks for the season

`data/usernames.txt` has been redacted for privacy reasons
