import random
import re
import sys
from collections import defaultdict, OrderedDict

import anilist

USERNAMES_FILE_NAME = './usernames.txt'
POOL_FILE_NAME = './pool.txt'


def _parse_file(file_name):
    with open(file_name, 'r') as file:
        data = file.read().strip()
        return data.split('\n')


if __name__ == '__main__':
    anilist_links = _parse_file(POOL_FILE_NAME)
    anilist_usernames_file = _parse_file(USERNAMES_FILE_NAME)

    anilist_usernames = []
    for u in anilist_usernames_file:
        # Simpler this way
        if u.lower().startswith('https://'):
            match = re.search(r'(?<=user/)([a-zA-Z0-9]+)/?', u)

            if not match:
                print(f'Not an anilist user: {u}', file=sys.stderr)
                continue

            match = match.group(1)
        else:
            match = u

        anilist_usernames.append(match)

    # We want to preserve the original insertion order
    anilist_users = OrderedDict((user_id, u) for u in anilist_usernames if u and (user_id := anilist.get_user_id(u)))
    anilist_media = {int(re.search(r'(?:anime|manga)/(\d+)/', link).group(1)): link for link in anilist_links}

    anilist_media_ids = list(anilist_media.keys())

    # Anime users haven't seen
    users_missing_media = anilist.get_missing_media(user_ids=list(anilist_users.keys()), media_ids=anilist_media_ids)

    selections = defaultdict(int)
    anilist_media_ids = set(anilist_media_ids)
    users_assigned_anime = anilist_users.copy()

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
