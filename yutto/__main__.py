import asyncio
import json
from typing import Any

import aiofiles
import aiohttp

from yutto.api.acg_video import get_acg_video_list, get_acg_video_playurl, get_acg_video_subtitile, get_video_info
from yutto.api.types import AId, BvId, CId
from yutto.media.quality import AudioQuality, VideoQuality, gen_video_quality_priority, gen_audio_quality_priority
from yutto.media.codec import VideoCodec, AudioCodec, gen_acodec_priority, gen_vcodec_priority
from yutto.utils.asynclib import LimitParallelsPool, run_with_n_workers
from yutto.utils.fetcher import Fetcher
from yutto.utils.file_buffer import AsyncFileBuffer, BufferChunk
from yutto.utils.logger import logger


def gen_headers():
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 Safari/537.36",
        "Referer": "https://www.bilibili.com",
    }

def select_video(
    videos: list[dict[str, Any]],
    video_quality: VideoQuality = 125,
    video_codec: VideoCodec = "hevc"
) -> dict[str, Any]:
    video_quality_priority = gen_video_quality_priority(video_quality)
    video_codec_priority = gen_vcodec_priority(video_codec)

    # fmt: off
    video_combined_priority = [
        (vqn, vcodec)
        for vqn in video_quality_priority
        for vcodec in video_codec_priority
    ]

    for vqn, vcodec in video_combined_priority:
        for video in videos:
            if video["quality"] == vqn and video["codec"] == vcodec:
                return video
    return {}

def select_audio(
    audios: list[dict[str, Any]],
    audio_quality: AudioQuality = 30280,
    audio_codec: AudioCodec = "mp4a",
) -> dict[str, Any]:
    audio_quality_priority = gen_audio_quality_priority(audio_quality)
    audio_codec_priority = gen_acodec_priority(audio_codec)

    # fmt: off
    audio_combined_priority = [
        (aqn, acodec)
        for aqn in audio_quality_priority
        for acodec in audio_codec_priority
    ]

    for aqn, acodec in audio_combined_priority:
        for audio in audios:
            if audio["quality"] == aqn and audio["codec"] == acodec:
                return audio
    return {}


async def main():

    async with aiohttp.ClientSession(headers=gen_headers(), timeout=aiohttp.ClientTimeout(total=5)) as sess:
        res = await get_video_info(sess, BvId("BV1864y1m7Yj"))
        print(res)
        print(json.dumps(str(res)))
        res = await get_video_info(sess, AId("887650906"))
        print(res)
        res = await get_acg_video_list(sess, AId("887650906"))
        print(res)
        res = await get_acg_video_subtitile(sess, BvId("BV1C4411J7cR"), CId("92109804"))
        print(res)
        videos, audios = await get_acg_video_playurl(sess, BvId("BV1C4411J7cR"), CId("92109804"))
        print(videos, audios)
        await Fetcher.get_size(sess, videos[0]["url"])
        video = select_video(videos)
        audio = select_audio(audios)
        print(video)
        print(audio)


# async def main():

#     buf = await AsyncFileBuffer.create('tt.txt')
#     await buf.write(b'12345', 25)
#     await buf.write(b'34567', 20)
#     await buf.write(b'00000', 30)
#     await buf.write(b'99999', 35)

#     await buf.close()

asyncio.run(main())
