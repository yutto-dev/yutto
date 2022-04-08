from .bangumi import BangumiExtractor
from .bangumi_batch import BangumiBatchExtractor
from .collection import CollectionExtractor
from .favourites import FavouritesExtractor
from .favourites_all import FavouritesAllExtractor
from .series import SeriesExtractor
from .ugc_video import UgcVideoExtractor
from .ugc_video_batch import UgcVideoBatchExtractor
from .uploader_all_videos import UploaderAllVideosExtractor

__all__ = [
    "UgcVideoExtractor",
    "UgcVideoBatchExtractor",
    "BangumiExtractor",
    "BangumiBatchExtractor",
    "UploaderAllVideosExtractor",
    "FavouritesExtractor",
    "FavouritesAllExtractor",
    "SeriesExtractor",
    "CollectionExtractor",
]
