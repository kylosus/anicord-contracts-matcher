import random
import re
import sys
import warnings
import csv
from collections import defaultdict, OrderedDict
from os import write
from pathlib import Path

import anilist
from anilist import User, AnilistEntry

# For convenience
DEFAULT_ANILIST_ENTRY = AnilistEntry(id=-1, url="***NOTHING***", jp_title="***NOTHING***",
                                     en_title="***NOTHING***", is_anime=False, is_trash=False)

USERNAMES_FILE_NAME = Path('./data/usernames.txt')
POOL_FILE_NAME = Path('./data/pool.txt')

anilist_pool: list[AnilistEntry] = []
anilist_users = OrderedDict()  # We want to preserve the original insertion order. This is to help Frazzle copy paste the output
staff_selections = defaultdict(int)
trash_selections = defaultdict(int)


def _parse_file(file_name: Path):
    with file_name.open(mode='r') as file:
        data = file.read().strip()
        return data.split('\n')


def select_anime(possible_media: list[AnilistEntry], score_episodes=True) -> AnilistEntry:
    if len(possible_media) == 0: return DEFAULT_ANILIST_ENTRY

    choices = random.choices(list(possible_media), k=len(possible_media))
    selections = trash_selections if possible_media[0].is_trash else staff_selections

    # Select the entry with the current lowest number of assignments
    # If score_episodes is set, it will use an alternate scoring system that prioritizes episode count
    # TODO: not clean
    if not score_episodes:
        choice, _ = min([(c, selections[c]) for c in choices], key=lambda x: x[1])
    else:
        # Specially handle division by 0 with an arbitrarily selected large number
        scores = [(0.2 * selections[c] + 0.8 * c.episodes) or 10e-9 for c in choices]
        inverted_scores = [1 / score for score in scores]
        choice = random.choices(choices, weights=inverted_scores, k=1)[0]

    selections[choice] += 1

    return choice


if __name__ == '__main__':
    anilist_links = _parse_file(POOL_FILE_NAME)
    anilist_usernames_file = _parse_file(USERNAMES_FILE_NAME)

    # Call anilist to get information about the anime we want to watch
    anilist_is_trash: dict[
        int, bool] = {}  # Look, I know it's not pythonic and all that, but it allows me to save expensive API calls or cycling through the file list again.

    for link in anilist_links:
        anilistId = int(re.search(r'(?:anime|manga)/(\d+)/', link).group(1))
        parts = link.partition(" | ")
        anilist_is_trash[anilistId] = parts[2] == "T"

    anilist_data = anilist.get_media_information(list(anilist_is_trash.keys()))

    for entry in anilist_data:
        anilist_id = int(entry["id"])  # Pre-extracting only things that need read multiple times for human readability.
        is_anime = entry["type"] == "ANIME"
        # Average number of episodes, for manga
        episodes = entry['episodes'] or 18  # TODO

        anilist_pool.append(AnilistEntry(
            id=anilist_id,
            url=entry["siteUrl"],
            jp_title=entry["title"]["romaji"],
            en_title=entry["title"]["english"],
            is_anime=is_anime,
            is_trash=anilist_is_trash[anilist_id],
            episodes=episodes)
        )

    # Get user ids for all participating members.
    for u in anilist_usernames_file:
        us = u.partition(" | ")
        if us[0].lower().startswith('https://'):
            match = re.search(r'(?<=user/)([a-zA-Z0-9]+)/?', u)

            if not match:
                print(f'Not an anilist user: {u}', file=sys.stderr)
                continue

            match = match.group(1)
        else:
            match = us[0]

        user_id = anilist.get_user_id(match)
        if user_id is None:
            print(f'Anilist user not found: {u}', file=sys.stderr)
            continue
        anilist_users[user_id] = anilist.User(id=int(user_id), username=match,
                                              flag=us[2] if us[2] else anilist.DEFAULT_CONTRACT_TYPE)

    # We now have the background information to allow us to start assigning anime.

    # both_users exists to allow us to do some optimizations around who gets what and disallowing double 2-cours.
    # These are in insertion order because anilist_users is an OrderedDict
    trash_users = [u for _, u in anilist_users.items() if u.flag in {"T", "B"}]
    staff_users = [u for _, u in anilist_users.items() if u.flag in {"S", "B"}]
    both_users = [u for _, u in anilist_users.items() if u.flag == "B"]

    trash_anime = set(filter(lambda m: m.is_trash, anilist_pool))
    special_anime = set(filter(lambda m: not m.is_trash, anilist_pool))

    # Get media present in users' lists
    staff_users_media = anilist.get_users_media(users=staff_users, media=special_anime)
    trash_users_media = anilist.get_users_media(users=trash_users, media=trash_anime)

    # Eligible selections for staff and trash users
    staff_users_eligible_media = {u: list(special_anime.difference(staff_users_media[u])) for u in staff_users}
    trash_users_eligible_media = {u: list(special_anime.difference(trash_users_media[u])) for u in trash_users}

    # Final assignments
    users_assigned_staff = dict[User, AnilistEntry]()
    users_assigned_trash = dict[User, AnilistEntry]()

    # Users that signed up for both get priority because Bpen says so (also because they're most likely to throw the selection balance out of whack).
    for user in both_users:
        # Merge both lists and randomly select one
        eligible_all = staff_users_eligible_media[user] + trash_users_eligible_media[user]

        # Alternatively can just select the lowest episode count, but it's more likely to assign manga
        # eligible_all_sorted = list(sorted(eligible_all, key=lambda m: m.episodes))
        # eligible_min_episodes = min(eligible_all, key=lambda m: m.episodes)

        # Just in case, make sure the list is unique
        assert list(set(eligible_all)) != list(eligible_all)

        # Select one short show
        # Bottom 33% of the shows for "better" randomness
        # An even better way would be to select randomly with inverse weights, but it's a little
        # more work and this is likely to perform fine
        # eligible_short = sorted(eligible_all, key=lambda m: m.episodes)[:len(eligible_all) // 2]

        # Assign one randomly. Remove from the eligible list
        media_short = select_anime(eligible_all, score_episodes=True)
        eligible_all.remove(media_short)

        # Select another random from the other list
        # Not really clean
        if media_short.is_trash:
            users_assigned_trash[user] = media_short
            media_other = select_anime(list(eligible_all))
            users_assigned_staff[user] = media_other
        else:
            users_assigned_staff[user] = media_short
            media_other = select_anime(list(eligible_all))
            users_assigned_trash[user] = media_other

    for u in staff_users:
        if u in both_users: continue
        media = select_anime(staff_users_eligible_media[u])
        users_assigned_staff[u] = media

    for u in trash_users:
        if u in both_users: continue
        media = select_anime(trash_users_eligible_media[u])
        users_assigned_trash[u] = media

    print("\nStaff/Veteran Specials:\n")


    def write_output(filename: str, assignments: dict[User, AnilistEntry]):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            csvwriter.writerow(['Username', 'Assigned Media', 'Type', 'Anilist Link'])
            for user, media in assignments.items():
                csvwriter.writerow([user.username, media.en_title if media.en_title else media.jp_title,
                                    'Anime' if media.is_anime else 'Manga', media.url])
                print(
                    f"{user.username}: \"{media.en_title if media.en_title else media.jp_title}\" {'Anime' if media.is_anime else 'Manga'}")


    write_output('data/assigned_staff.csv', users_assigned_staff)
    write_output('data/assigned_trash.csv', users_assigned_trash)

    print("\n------------------------------------\nStats:\n")
    missing_staff_list = [u for u in users_assigned_staff if users_assigned_staff[u] == -1]
    print(f"Users not Assigned a staff/veteran special: {len(missing_staff_list)}")

    if len(missing_staff_list) > 0:
        for u in missing_staff_list:
            print(u.username)

    missing_trash_list = [u for u in users_assigned_trash if users_assigned_trash[u] == -1]
    print(f"\nUsers not Assigned a trash special: {len(missing_trash_list)}")

    if len(missing_trash_list) > 0:
        for u in missing_staff_list:
            print(u.username)

    print("\n------------------------------------\nAssignment Counts:\n")
    print("Staff/Veteran Specials:")
    for a in special_anime:
        print(f"anilist id: {a.id}, title: {a.en_title if a.en_title else a.jp_title}, count: {staff_selections[a]}")

    print("\nTrash Specials:")
    for a in trash_anime:
        print(f"{a.en_title if a.en_title else a.jp_title}: {trash_selections[a]}")

    # print("\n------------------------------------\nLength Check for users assigned from both lists:\n")
    # for u in both_users:
    #     if users_assigned_staff[u].episodes > 16 and users_assigned_trash[u].episodes > 16:
    #         warnings.warn(f"User: {u.username.ljust(20)} was assigned two long anime shows. Please double check this! (there should be another warning higher in the console for this same user)")
    #     elif users_assigned_staff[u].episodes > 16 or users_assigned_trash[u].episodes > 16:
    #         print(f"User: {u.username.ljust(20)} was assigned one long and one short show")
    #     else:
    #         print(f"User: {u.username.ljust(20)} was assigned two shorts shows")
