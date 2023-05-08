import random
import re

import anilist

USERNAMES_FILE_NAME = './usernames.txt'
POOL_FILE_NAME = './pool.txt'


def _parse_file(file_name):
    with open(file_name, 'r') as file:
        data = file.read()
        return data.split('\n')


if __name__ == '__main__':
    anilist_links = _parse_file(POOL_FILE_NAME)
    anilist_usernames_file = _parse_file(USERNAMES_FILE_NAME)

    anilist_usernames = []
    for u in anilist_usernames_file:
        # Simpler this way
        if u.startswith('https://'):
            match = re.search(r'(?<=user/)([a-zA-Z0-9]+)/?', u)

            if not match:
                print(f'Did not match {u}')
                continue

            match = match.group(1)
        else:
            match = u

        anilist_usernames.append(match)

    anilist_users = {user_id: u for u in anilist_usernames if (user_id := anilist.get_user_id(u))}
    anilist_media = {int(re.search(r'anime/(\d+)/', link).group(1)): link for link in anilist_links}

    anilist_media_ids = list(anilist_media.keys())

    # Anime users haven't seen
    users_missing_media = anilist.get_missing_media(user_ids=list(anilist_users.keys()), media_ids=anilist_media_ids)

    anilist_media_ids = set(anilist_media_ids)

    for user_id, media_list in users_missing_media.items():
        possible_media = anilist_media_ids.difference((x[0] for x in media_list))

        if len(possible_media) == 0:
            print(f'Nothing to recommend to {anilist_users[user_id]}')
            continue

        print(f'{anilist_media[random.choice(list(possible_media))]} for {anilist_users[user_id]}')
