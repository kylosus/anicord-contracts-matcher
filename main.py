import random
import re
import sys
from collections import defaultdict, OrderedDict
from pathlib import Path

import anilist
from anilist import AnilistEntry

USERNAMES_FILE_NAME = Path('./data/usernames.txt')
POOL_FILE_NAME = Path('./data/pool.txt')

anilist_media_information = dict[int, AnilistEntry]()
anilist_users = OrderedDict() # We want to preserve the original insertion order, this means that older anilist users don't have an "advantage"
staff_selections = defaultdict(int)
trash_selections = defaultdict(int)

def _parse_file(file_name: Path):
    with file_name.open(mode='r') as file:
        data = file.read().strip()
        return data.split('\n')


def select_anime(possible_media: list[int], is_trash: bool = False) -> int:
    if len(possible_media) == 0: return -1
    choices = random.choices(list(possible_media), k=len(possible_media))

    choice = choices[0]
    for c in choices[1:]:
        if c == -1: continue
        if is_trash and trash_selections[c] < trash_selections[choice]: choice = c
        if not is_trash and staff_selections[c] < staff_selections[choice]: choice = c

    if is_trash:
        trash_selections[choice] += 1
    else:
        staff_selections[choice] += 1
    return choice

if __name__ == '__main__':
    anilist_links = _parse_file(POOL_FILE_NAME)
    anilist_usernames_file = _parse_file(USERNAMES_FILE_NAME)

    #Call anilist to get information about the anime we want to watch
    anilist_isTrash: dict[int, bool] =  {} #Look, I know it's not pythonic and all that, but it allows me to save expensive API calls or cycling through the file list again.

    for link in anilist_links:
        anilistId = int(re.search(r'(?:anime|manga)/(\d+)/', link).group(1))
        parts = link.partition(" | ")
        anilist_isTrash[anilistId] = parts[2] == "T"

    anilist_data = anilist.get_media_information(list(anilist_isTrash.keys()))

    for entry in anilist_data:
        item_id = int(entry["id"]) #Pre-extracting only things that need read multiple times for human readability.
        isAnime = entry["type"] == "ANIME"
        isLongAnime = False if not isAnime else entry["episodes"] >= 16
        anilist_media_information[item_id] = anilist.AnilistEntry(
            item_id=item_id,
            url=entry["siteUrl"],
            jp_title=entry["title"]["romaji"],
            en_title = entry["title"]["english"],
            isAnime=isAnime,
            isLongAnime=isLongAnime,
            isTrash=anilist_isTrash[item_id])

    #Get user ids for all participating members.
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

        print(f"Getting id for user: {match}")
        user_id = anilist.get_user_id(match)
        print(f"user_id: {user_id}")
        if user_id is None:
            print(f'Anilist user not found: {u}', file=sys.stderr)
            continue
        anilist_users[user_id] = anilist.User(id=int(user_id), username=match, flag=us[2] if us[2] else anilist.DEFAULT_CONTRACT_TYPE)

    # We now have the background information to allow us to start assigning anime.

    # both_users exists to allow us to do some optimizations around who gets what and disallowing double 2-cours.
    # These are in insertion order because anilist_users is an OrderedDict
    trash_users = [u for _, u in anilist_users.items() if u.flag in {"T", "B"}]
    staff_users = [u for _, u in anilist_users.items() if u.flag in {"S", "B"}]
    both_users = [u for _, u in anilist_users.items() if u.flag == "B"]

    trash_anime = set(filter(lambda m: m.isTrash, anilist_pool))
    special_anime = set(filter(lambda m: not m.isTrash, anilist_pool))

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

    for user_id in both_users:
        # First check both lists and see if one of them only contains long shows.
        # If so, we'll select from that list first, and limit the other half to short shows.
        # Note: a user can still receive two long shows if that's all they're eligible for.

        elig_short_staff = [int(k) for k in staff_media_users_eligible_for[user_id] if not anilist_media_information[k].isLongAnime]
        elig_short_trash = [int(k) for k in trash_media_users_eligible_for[user_id] if not anilist_media_information[k].isLongAnime]

        # Flip a coin to see what will get assigned first
        trash_first = random.randint(0, 1) == 1
        force_two_long = False

        # Override the coin if needed, if they're unlucky enough to be forced into two long shows we'll abide by the coin, not that it really matters
        # How this works:
        # If a user has eligible short entries on both sides, we abide by the coin.
        #   If they pull a short show (or manga) in their first pull it uses their entire list for the second pull as well, they might end up with two short, who knows.
        #   If they pull a long show on their first pull we reduce the pool to just short shows (and manga) for the second pull.
        # If a user is going to be forced to have a long show for one type (but has eligible short/manga in the other) we force the pull on the long side first.
        #   This then means the check for a long show is triggered, and we automatically use the short list on the other one
        # If a User has no eligible short shows/manga on either side we set the `force_two_long` bool to true. So that when they are assigned their shows it doesn't try to give them nothing on the second one.
        if len(elig_short_staff) == 0 and len(elig_short_trash) == 0: force_two_long = True
        elif len(elig_short_staff) == 0: trash_first = False
        elif len(elig_short_trash) == 0: trash_first = True

        if trash_first:
            first_anime = select_anime(trash_media_users_eligible_for[user_id], True)
            users_assigned_trash[user_id] = first_anime
            second_anime = -1
            if first_anime != -1 and anilist_media_information[first_anime].isLongAnime and not force_two_long:
                second_anime = select_anime(elig_short_staff, False)
            else:
                second_anime = select_anime(staff_media_users_eligible_for[user_id], False)
            users_assigned_staff[user_id] = second_anime
        else:
            first_anime = select_anime(staff_media_users_eligible_for[user_id], False)
            users_assigned_staff[user_id] = first_anime
            second_anime = -1
            if first_anime != -1 and anilist_media_information[first_anime].isLongAnime and not force_two_long:
                second_anime = select_anime(elig_short_trash, True)
            else:
                second_anime = select_anime(trash_media_users_eligible_for[user_id], True)
            users_assigned_trash[user_id] = second_anime

    # That's the hard stuff out of the way. Now for the much easier steps of finishing assigning staff/veterans and then trash.

    for u in staff_users:
        if u in both_users: continue
        media = select_anime(staff_users_eligible_media[u])
        users_assigned_staff[u] = media

    for u in trash_users:
        if u in both_users: continue
        media = select_anime(trash_users_eligible_media[u])
        users_assigned_trash[u] = media

    print("\nStaff/Veteran Specials:\n")
    for user, media in users_assigned_staff.items():
        print(f"{user.username}: \"{media.en_title if media.en_title else media.jp_title}\" {'Anime' if media.isAnime else 'Manga'}")

    print("\n------------------------------------\nTrash Specials:\n")
    for user, media in users_assigned_trash.items():
        print(f"{user.username}: \"{media.en_title if media.en_title else media.jp_title}\" {'Anime' if media.isAnime else 'Manga'}")

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