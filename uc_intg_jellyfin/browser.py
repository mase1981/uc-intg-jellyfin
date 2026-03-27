"""
Media browser for Jellyfin integration.

:copyright: (c) 2025-2026 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ucapi import StatusCodes
from ucapi.api_definitions import (
    BrowseMediaItem,
    BrowseOptions,
    BrowseResults,
    MediaClass,
    Pagination,
    SearchOptions,
    SearchResults,
)

if TYPE_CHECKING:
    from uc_intg_jellyfin.device import JellyfinDevice

_LOG = logging.getLogger(__name__)

PAGE_SIZE = 50

_TYPE_TO_CLASS = {
    "Movie": MediaClass.MOVIE,
    "Series": MediaClass.TV_SHOW,
    "Season": MediaClass.DIRECTORY,
    "Episode": MediaClass.EPISODE,
    "Audio": MediaClass.TRACK,
    "MusicAlbum": MediaClass.ALBUM,
    "MusicArtist": MediaClass.ARTIST,
    "CollectionFolder": MediaClass.DIRECTORY,
    "Folder": MediaClass.DIRECTORY,
    "Playlist": MediaClass.PLAYLIST,
}

_PLAYABLE_TYPES = {"Movie", "Episode", "Audio"}
_BROWSABLE_TYPES = {"Series", "Season", "MusicAlbum", "MusicArtist", "CollectionFolder", "Folder", "Playlist"}


async def browse(
    device: JellyfinDevice, device_id: str, options: BrowseOptions
) -> BrowseResults | StatusCodes:
    media_type = options.media_type or "root"
    media_id = options.media_id or ""

    if media_type == "root" or (options.media_id is None and options.media_type is None):
        return _browse_root(device)

    if media_type == "libraries":
        return _browse_libraries(device)

    if media_type == "library" and media_id:
        paging = options.paging
        page = int((paging.page if paging and paging.page else None) or 1)
        return _browse_library(device, media_id, page)

    if media_type in ("series", "season", "artist", "album", "folder") and media_id:
        paging = options.paging
        page = int((paging.page if paging and paging.page else None) or 1)
        return _browse_container(device, media_id, page)

    return StatusCodes.NOT_FOUND


async def search(
    device: JellyfinDevice, device_id: str, options: SearchOptions
) -> SearchResults | StatusCodes:
    query = (options.query or "").strip()
    if not query:
        return SearchResults(media=[], pagination=Pagination(page=1, limit=0, count=0))

    results = device.search_items(query, limit=PAGE_SIZE)

    items = []
    for item in results:
        item_type = item.get("Type", "")
        media_class = _TYPE_TO_CLASS.get(item_type, MediaClass.DIRECTORY)
        can_play = item_type in _PLAYABLE_TYPES
        can_browse = item_type in _BROWSABLE_TYPES

        browse_type = _get_browse_type(item_type)
        image = device.get_artwork_url(item, max_width=300) or ""

        title = _format_title(item)

        items.append(BrowseMediaItem(
            title=title,
            media_class=media_class,
            media_type=browse_type,
            media_id=f"item_{item['Id']}" if can_play else item["Id"],
            can_play=can_play,
            can_browse=can_browse,
            image_url=image,
        ))

    return SearchResults(
        media=items,
        pagination=Pagination(page=1, limit=len(items), count=len(items)),
    )


def _browse_root(device: JellyfinDevice) -> BrowseResults:
    libraries = device.get_libraries()
    lib_items = []
    for lib in libraries:
        image = device.get_artwork_url(lib, max_width=300) or ""
        lib_items.append(BrowseMediaItem(
            title=lib.get("Name", "Library"),
            media_class=MediaClass.DIRECTORY,
            media_type="library",
            media_id=lib["Id"],
            can_browse=True,
            can_play=False,
            image_url=image,
        ))

    return BrowseResults(
        media=BrowseMediaItem(
            title="Jellyfin",
            media_class=MediaClass.DIRECTORY,
            media_type="root",
            media_id="root",
            can_browse=True,
            items=lib_items,
        ),
        pagination=Pagination(page=1, limit=len(lib_items), count=len(lib_items)),
    )


def _browse_libraries(device: JellyfinDevice) -> BrowseResults:
    return _browse_root(device)


def _browse_library(device: JellyfinDevice, library_id: str, page: int) -> BrowseResults:
    start_index = (page - 1) * PAGE_SIZE
    result = device.get_items(library_id, limit=PAGE_SIZE, start_index=start_index)

    items_data = result.get("Items", [])
    total = result.get("TotalRecordCount", len(items_data))

    items = _items_to_browse_items(device, items_data)

    return BrowseResults(
        media=BrowseMediaItem(
            title="Library",
            media_class=MediaClass.DIRECTORY,
            media_type="library",
            media_id=library_id,
            can_browse=True,
            can_search=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


def _browse_container(device: JellyfinDevice, container_id: str, page: int) -> BrowseResults:
    start_index = (page - 1) * PAGE_SIZE
    result = device.get_items(container_id, limit=PAGE_SIZE, start_index=start_index)

    items_data = result.get("Items", [])
    total = result.get("TotalRecordCount", len(items_data))

    items = _items_to_browse_items(device, items_data)

    return BrowseResults(
        media=BrowseMediaItem(
            title="Browse",
            media_class=MediaClass.DIRECTORY,
            media_type="folder",
            media_id=container_id,
            can_browse=True,
            items=items,
        ),
        pagination=Pagination(page=page, limit=PAGE_SIZE, count=total),
    )


def _items_to_browse_items(device: JellyfinDevice, items: list[dict]) -> list[BrowseMediaItem]:
    result = []
    for item in items:
        item_type = item.get("Type", "")
        media_class = _TYPE_TO_CLASS.get(item_type, MediaClass.DIRECTORY)
        can_play = item_type in _PLAYABLE_TYPES
        can_browse = item_type in _BROWSABLE_TYPES

        browse_type = _get_browse_type(item_type)
        image = device.get_artwork_url(item, max_width=300) or ""
        title = _format_title(item)

        result.append(BrowseMediaItem(
            title=title,
            media_class=media_class,
            media_type=browse_type,
            media_id=f"item_{item['Id']}" if can_play else item["Id"],
            can_play=can_play,
            can_browse=can_browse,
            image_url=image,
        ))
    return result


def _get_browse_type(item_type: str) -> str:
    mapping = {
        "Series": "series",
        "Season": "season",
        "MusicArtist": "artist",
        "MusicAlbum": "album",
        "CollectionFolder": "library",
        "Folder": "folder",
        "Playlist": "folder",
    }
    return mapping.get(item_type, "item")


def _format_title(item: dict) -> str:
    name = item.get("Name", "Unknown")
    item_type = item.get("Type", "")

    if item_type == "Episode":
        series = item.get("SeriesName", "")
        se = ""
        if item.get("ParentIndexNumber") is not None and item.get("IndexNumber") is not None:
            se = f"S{item['ParentIndexNumber']}E{item['IndexNumber']} - "
        if series:
            return f"{series} {se}{name}"
        return f"{se}{name}"

    if item_type == "Season":
        series = item.get("SeriesName", "")
        if series:
            return f"{series} - {name}"

    return name
