import os.path

import dicttoxml
from xml.dom.minidom import parseString

from yutto.typing import EpisodeData


def save_season_metadata_file(episode_data: EpisodeData, ext: str = "nfo"):
    output_dir = episode_data["output_dir"]
    filename = episode_data["filename"] + "." + ext
    metadata = episode_data["metadata"]

    save(output_dir, filename, metadata, custom_root="tvshow")


def save_episode_metadata_file(episode_data: EpisodeData, ext: str = "nfo"):
    output_dir = episode_data["output_dir"]
    filename = episode_data["filename"] + "." + ext
    metadata = episode_data["metadata"]

    save(output_dir, filename, metadata)


def save(dir: str, filename: str, data, encoding="utf8", custom_root="episodedetails"):
    path = os.path.join(dir, filename)

    if not os.path.exists(dir):
        os.makedirs(dir)

    xml = dicttoxml.dicttoxml(data, custom_root=custom_root, attr_type=False)
    dom = parseString(xml)
    pretty_content = dom.toprettyxml()
    f = open(path, "w", encoding=encoding)
    f.write(pretty_content)
    f.close()

