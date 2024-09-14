import sys
import time
from collections import defaultdict
from dataclasses import dataclass

import requests
from mezmorize import Cache

DEFAULT_CONTRACT_TYPE = "S"


@dataclass(frozen=True)
class AnilistItem:
    id: int

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


@dataclass(frozen=True)
class User(AnilistItem):
    """
    An anicord user.
    Attributes:
        username (str): The username of the user.
        flag (str): Flag for contracts type.
            Valid values: `S` (for Staff/Veteran Specials), `T` (for Trash Specials), `B` (for Both).
            The parser will use DEFAULT_CONTRACT_TYPE if a value is not specified in the file.
        user_id: The users id on Anilist.
    """
    username: str
    flag: str


@dataclass(frozen=True)
class AnilistEntry(AnilistItem):
    """
    An entry on Anilist
    Attributes:
        item_id (int): The item id on Anilist
        url (str): Canonical URL of the item.
        jp_title (str): The title of the item in romaji.
        en_title (str): The title of the item in English.
        isAnime: Whether the item is an anime (true) or manga (false).
        isTrash: Whether the entry is for Trash Specials (true) or Staff/Veteran Specials (false).
        isLongAnime: Whether the anime is 16+ Episodes, should always be false if isAnime is false.
    """
    url: str
    jp_title: str
    en_title: str
    is_anime: bool
    is_trash: bool
    episodes: int = 0


# Cache for 1 year because the library hates me
cache = Cache(CACHE_TYPE='filesystem', CACHE_DIR='cache', CACHE_DEFAULT_TIMEOUT=365 * 24 * 60 * 60)

URL_BASE = 'https://graphql.anilist.co'

GET_USER_LIST_QUERY = """
query($userName: String, $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo {
        hasNextPage
    }
    mediaList(userName: $userName) {
      id
      status
      progress
      media {
       id
        title {
          userPreferred
        }
      }
    }
  }
}
"""

GET_MEDIA_INFORMATION_query = """
query ($page: Int, $mediaIds: [Int]) {
  Page(page: $page, perPage: 50) {
    pageInfo {
      hasNextPage
    }
    media(id_in: $mediaIds) {
      id
      siteUrl
      episodes
      type
      title {
        romaji
        english
      }
    }
  }
}
"""

# Reducing amount of data pulled to a bare minimum. This is all the data we need to make determinations.
GET_MEDIA_IN_USERS_LIST_query = """
query ($page: Int, $userIds: [Int], $mediaIds: [Int]) {
  Page(page: $page, perPage: 50) {
    pageInfo {
      hasNextPage
    }
    mediaList(userId_in: $userIds, mediaId_in: $mediaIds) {
      user {
        id
      }
      status
      media {
        id
      }
    }
  }
}
"""

GET_USER_ID_QUERY = """
query($userName: String) {
  User(name: $userName) {
    id
  }
}
"""


def _get_all_pages(query, variables, *, query_field='mediaList', _page=0):
    response = _make_request(query, variables={**variables, 'page': _page})

    # Can make this asynchronous
    data = response['data']['Page']
    has_next_page = data['pageInfo']['hasNextPage']
    query_list = data[query_field]

    if has_next_page:
        print(f'next {_page}')
        return list([*query_list, *_get_all_pages(query, variables, _page=_page + 1)])

    return list(query_list)


def _make_request(query: str, variables: dict):
    # retry on 429 after time specified in the response:
    while True:
        response = requests.post(url=URL_BASE, json={
            'query': query,
            'variables': variables
        })

        if response.status_code != 429:
            break

        # Per the docs, going over the rate limit leads to a 1-minute timeout. a 429 should also have a `Retry-After` header.
        # Timeout is set at 62 seconds to ensure that we wait at least the minimum time even if the header doesn't exist.
        # If the header does exist we'll use the value provided by it.
        # Both values are padded an extra 2 seconds to make sure we don't end up making the request just before the timeout is lifted.
        timeout_seconds = 62
        if "Retry-After" in response.headers:
            timeout_seconds = int(response.headers["Retry-After"]) + 2

        print(f'429: {response}. Waiting {timeout_seconds} seconds...', file=sys.stderr)
        time.sleep(timeout_seconds)

    time.sleep(0.7)  # This should _theoretically_ mean we never hit the 429 again.
    return response.json()


def get_users_media(users: list[User], media: set[AnilistEntry]) -> defaultdict[User, list[AnilistEntry]]:
    # Sorting for caching
    user_ids = [u.id for u in users]
    media_ids = [m.id for m in media]
    data = _get_media_users_are_ineligible_for(sorted(user_ids), sorted(media_ids))

    # Default dicts are great.
    user_dict = defaultdict(list)
    for list_item in data:
        if list_item["status"] == 'PLANNING': continue
        user_dict[int(list_item['user']['id'])].append(int(list_item['media']['id']))

    return user_dict


def get_media_information(media_ids: list[int]):
    return _get_media_information(sorted(media_ids))


@cache.memoize()
def get_user_id(user_name: str) -> int | None:
    response = _make_request(query=GET_USER_ID_QUERY, variables={
        'userName': user_name
    })

    if 'errors' in response and len(response['errors']) != 0:
        print(f'{user_name} not found ({response})', file=sys.stderr)
        return None

    return response['data']['User']['id']


@cache.memoize()
def _get_media_information(media_ids: list[int]):
    return _get_all_pages(query=GET_MEDIA_INFORMATION_query, query_field="media", variables={'mediaIds': media_ids})


@cache.memoize()
def _get_media_users_are_ineligible_for(user_ids: list[int], media_ids: list[int]) -> list:
    return _get_all_pages(query=GET_MEDIA_IN_USERS_LIST_query, variables={
        'userIds': user_ids,
        'mediaIds': media_ids
    })
