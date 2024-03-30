from __future__ import annotations

# import pytest
from yutto.utils.ffmpeg import FFmpegCommandBuilder


def test_video_input_only():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.m4s", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_audio_input_only():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_audio_input("input.aac")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.aac", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_auto_stream_selection():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    command_builder.add_output("output.mp4")
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_manual_stream_selection_select_all():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    output.use(audio_input)
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "-map", "0", "-map", "1", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_manual_stream_selection_select_video_only():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    excepted_command = ["-i", "input.m4s", "-i", "input.aac", "-map", "0", "--", "output.mp4"]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_cover():
    command_builder = FFmpegCommandBuilder()
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    cover_input = command_builder.add_video_input("cover.jpg")
    output = command_builder.add_output("output.mp4")
    output.use(video_input)
    output.use(audio_input)
    output.use(cover_input)
    output.set_cover(cover_input)
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-i",
        "cover.jpg",
        "-map",
        "0",
        "-map",
        "1",
        "-map",
        "2",
        "-c:v:1",
        "copy",
        "-disposition:v:1",
        "attached_pic",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_cover_reorder():
    command_builder = FFmpegCommandBuilder()
    cover_input = command_builder.add_video_input("cover.jpg")
    video_input = command_builder.add_video_input("input.m4s")
    audio_input = command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.use(cover_input)
    output.use(audio_input)
    output.use(video_input)
    output.set_cover(cover_input)
    excepted_command = [
        "-i",
        "cover.jpg",
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-map",
        "0",
        "-map",
        "2",
        "-map",
        "1",
        "-c:v:0",
        "copy",
        "-disposition:v:0",
        "attached_pic",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_codec():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.set_vcodec("hevc")
    output.set_acodec("copy")
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-vcodec",
        "hevc",
        "-acodec",
        "copy",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command


def test_merge_video_audio_with_extra_options():
    command_builder = FFmpegCommandBuilder()
    command_builder.add_video_input("input.m4s")
    command_builder.add_audio_input("input.aac")
    output = command_builder.add_output("output.mp4")
    output.with_extra_options(["-strict", "unofficial"])
    command_builder.with_extra_options(["-threads", "8"])
    excepted_command = [
        "-i",
        "input.m4s",
        "-i",
        "input.aac",
        "-threads",
        "8",
        "-strict",
        "unofficial",
        "--",
        "output.mp4",
    ]
    assert command_builder.build() == excepted_command
