import random
import re
import sys
from collections import defaultdict, OrderedDict
from pathlib import Path

import anilist

USERNAMES_FILE_NAME = Path('./data/usernames.txt')
POOL_FILE_NAME = Path('./data/pool.txt')

selections = defaultdict(int)
special_selections = defaultdict(int)
trash_selections = defaultdict(int)

def _parse_file(file_name: Path):
    with file_name.open(mode='r') as file:
        data = file.read().strip()
        return data.split('\n')


def select_anime(user_id: int, missing_media, media_list, avoid_long: bool = False, is_trash: bool = False):
    possible_media = missing_media.difference((x[0] for x in media_list))
    choices = random.choices(list(possible_media), k=len(possible_media))
    choice = min([(c, trash_selections[c] if is_trash else special_selections[c]) for c in choices], key=lambda x: x[1])
    if is_trash:
        trash_selections[choice[0]] += 1
    else :
        special_selections[choice[0]] += 1
    return choice[0]

if __name__ == '__main__':
    anilist_links = _parse_file(POOL_FILE_NAME)
    anilist_usernames_file = _parse_file(USERNAMES_FILE_NAME)

    anilist_usernames = []
    for u in anilist_usernames_file:
        # Simpler this way
        us = u.partition(" | ")
        if us[0].lower().startswith('https://'):
            match = re.search(r'(?<=user/)([a-zA-Z0-9]+)/?', u)

            if not match:
                print(f'Not an anilist user: {u}', file=sys.stderr)
                continue

            match = match.group(1)
        else:
            match = us[0]

        anilist_usernames.append(anilist.User(match, us[2], anilist.get_user_id(match)))

    # We want to preserve the original insertion order
    anilist_users = OrderedDict((user_id, u) for u in anilist_usernames if u and (user_id := anilist.get_user_id(u)))

    anilist_media = {}

    for link in anilist_links:
        anilistId = int(re.search(r'(?:anime|manga)/(\d+)/', link).group(1))
        parts = link.partition(" | ")
        anilist_media[anilistId] = anilist.AnilistEntry(parts[0], parts[2] == "T")

    # both_users exists to allow us to do some optimizations around who gets what and disallowing double 2-cours.
    trash_users = sorted([u.user_id for u in anilist_usernames if u.flag in {"T", "B"}])
    special_users = sorted([u.user_id for u in anilist_usernames if u.flag in {"S", "B"}])
    both_users = sorted([u.user_id for u in anilist_usernames if u.flag == "B"])


    trash_anime = [kvp[0] for kvp in anilist_media.items() if kvp[1].isTrash]
    special_anime = [kvp[0] for kvp in anilist_media.items() if not kvp[1].isTrash]
    # Anime users haven't seen
    users_missing_staff_media = anilist.get_missing_media(user_ids=list(anilist_users.keys()), media_ids=special_anime)
    users_missing_trash_media = anilist.get_missing_media(user_ids=trash_users, media_ids=trash_anime)

    users_assigned_specials = {}
    users_assigned_trash = {}

    # Users that signed up for both get priority because Bpen says so.

    for user_id in both_users:
        trash_first = random.randint(0, 1) == 1
        first_anime = None
        if trash_first:
            first_anime = select_anime(user_id, users_missing_trash_media[])

    for user_id, media_list in sorted(users_missing_media.items()):
        possible_media = anilist_media_ids.difference((x[0] for x in media_list))

        if len(possible_media) == 0:
            print(f'{anilist_users[user_id]},*Nothing*')
            continue

        # Flatten the distribution
        choices = random.choices(list(possible_media), k=len(possible_media))
        choice = min([(c, selections[c]) for c in choices], key=lambda x: x[1])
        selections[choice[0]] += 1

        users_assigned_anime[user_id] = f'{anilist_users[user_id]},{anilist_media[choice[0]]}'

    print('\n'.join(users_assigned_anime.values()))

    print()
    print('Stats:')

    sorted_selections = sorted(selections.items(), key=lambda x: x[1], reverse=True)
    selected_media = [anilist_media[k] for k in selections.keys()]

    for k, c in sorted(selections.items()):
        print(f'{anilist_media[k]}: {c}')

    print(f'Total: {len(selections)}/{len(anilist_media)}')
    print('Missing:')
    print('\n'.join(list(set(anilist_media.values()).difference(selected_media))))
