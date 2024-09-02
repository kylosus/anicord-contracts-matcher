import sys
import time
from typing import NamedTuple

import requests
from mezmorize import Cache


class User(NamedTuple):
    username: str
    flag: str
    user_id: int


class AnilistEntry(NamedTuple):
    url: str
    isTrash: bool


# Cache for 1 year because the library hates me
cache = Cache(CACHE_TYPE='filesystem', CACHE_DIR='cache', CACHE_DEFAULT_TIMEOUT=365 * 24 * 60 * 60)

URL_BASE = 'https://graphql.anilist.co'


def _make_request(query: str, variables: dict, timeout_seconds=5):
    # retry on 429:
    while True:
        response = requests.post(url=URL_BASE, json={
            'query': query,
            'variables': variables
        })

        if response.status_code != 429:
            break

        print(f'429: {response}. Waiting {timeout_seconds} seconds...', file=sys.stderr)
        time.sleep(timeout_seconds)
        timeout_seconds *= 2

    return response.json()


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


def medialist_to_tuple(media_list):
    media_list = filter(lambda m: m['status'] != 'PLANNING', media_list)
    return list(map(lambda m: (m['media']['id'], m['media']['title']['userPreferred'], m['media']['type'], m['media']['episodes']), media_list))


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


@cache.memoize()
def get_user_list(user_name: str) -> list:
    return medialist_to_tuple(_get_all_pages(query=GET_USER_LIST_QUERY, variables={'userName': user_name}))


GET_USER_ID_QUERY = """
query($userName: String) {
  User(name: $userName) {
    id
  }
}
"""


@cache.memoize()
def get_user_id(user: User) -> int | None:
    response = _make_request(query=GET_USER_ID_QUERY, variables={
        'userName': user.username
    })

    if 'errors' in response and len(response['errors']) != 0:
        print(f'{user.username} not found ({response})', file=sys.stderr)
        return None

    return response['data']['User']['id']


GET_MISSING_MEDIA_query = """
query($page: Int,  $userIds: [Int], $mediaIds: [Int]) {
  Page(page: $page, perPage: 50) {
    pageInfo {
        hasNextPage
    }
    mediaList(userId_in: $userIds, mediaId_in: $mediaIds) {
      user {
        id
        name
      }
      status
      media {
        status
        id
        episodes
        type
        title {
          userPreferred
        }
      }
    }
  }
}
"""


def get_missing_media(user_ids: [int], media_ids: [int]):
    # Sorting for caching
    return _get_missing_media(sorted(user_ids), sorted(media_ids))


@cache.memoize()
def _get_missing_media(user_ids: [int], media_ids: [int]):
    data = _get_all_pages(query=GET_MISSING_MEDIA_query, variables={
        'userIds': user_ids,
        'mediaIds': media_ids
    })

    # Initialize with all user ids.
    user_dict = {k: [] for k in user_ids}

    for media_list in data:
        user_dict[media_list['user']['id']].append(media_list)

    for k, v in user_dict.items():
        user_dict[k] = medialist_to_tuple(v)

    return user_dict
