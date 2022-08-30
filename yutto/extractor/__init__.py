from __future__ import annotations

from .bangumi import BangumiExtractor
from .bangumi_batch import BangumiBatchExtractor
from .collection import CollectionExtractor
from .favourites import FavouritesExtractor
from .series import SeriesExtractor
from .ugc_video import UgcVideoExtractor
from .ugc_video_batch import UgcVideoBatchExtractor
from .user_all_favourites import UserAllFavouritesExtractor
from .user_all_ugc_videos import UserAllUgcVideosExtractor

__all__ = [
    "UgcVideoExtractor",
    "UgcVideoBatchExtractor",
    "BangumiExtractor",
    "BangumiBatchExtractor",
    "UserAllUgcVideosExtractor",
    "FavouritesExtractor",
    "UserAllFavouritesExtractor",
    "SeriesExtractor",
    "CollectionExtractor",
]
