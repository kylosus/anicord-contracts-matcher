from collections import defaultdict

import requests
from mezmorize import Cache

cache = Cache(CACHE_TYPE='filesystem', CACHE_DIR='cache')

URL_BASE = 'https://graphql.anilist.co'


def _make_request(query: str, variables: dict):
    return requests.post(url=URL_BASE, json={
        'query': query,
        'variables': variables
    }).json()


def medialist_to_tuple(media_list):
    media_list = filter(lambda m: m['status'] != 'PLANNING', media_list)
    return list(map(lambda m: (m['media']['id'], m['media']['title']['userPreferred']), media_list))


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
def get_user_list(user_name: str, _page: int = 0) -> list:
    return _get_user_list(user_name, _page)


def _get_user_list(user_name: str, _page: int = 0) -> list:
    response = _make_request(query=GET_USER_LIST_QUERY, variables={
        'userName': user_name,
        'page': _page
    })

    data = response['data']['Page']
    has_next_page = data['pageInfo']['hasNextPage']
    media_list = medialist_to_tuple(data['mediaList'])

    if has_next_page:
        print(f'next {_page}')
        return list([*media_list, *_get_user_list(user_name, _page + 1)])

    return list(media_list)


GET_USER_ID_QUERY = """
query($userName: String) {
  User(name: $userName) {
    id
  }
}
"""


@cache.memoize()
def get_user_id(user_name: str) -> int | None:
    response = _make_request(query=GET_USER_ID_QUERY, variables={
        'userName': user_name
    })

    if 'errors' in response and len(response['errors']) != 0:
        print(f'{user_name} not found')
        return None

    return response['data']['User']['id']


GET_MISSING_MEDIA_query = """
query($userIds: [Int], $mediaIds: [Int]) {
  Page(page: 0, perPage: 50) {
    mediaList(userId_in: $userIds, mediaId_in: $mediaIds) {
      user {
        id
        name
      }
      status
      media {
        status
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
def get_missing_media(user_ids: [int], media_ids: [int]):
    response = _make_request(query=GET_MISSING_MEDIA_query, variables={
        'userIds': user_ids,
        'mediaIds': media_ids
    })

    data = response['data']['Page']

    # Initialize with all user ids. Doesn't have to be defaultdict
    user_dict = defaultdict(list, {k: [] for k in user_ids})

    for media_list in data['mediaList']:
        user_dict[media_list['user']['id']].append(media_list)

    for k, v in user_dict.items():
        user_dict[k] = medialist_to_tuple(v)

    return user_dict
