from yutto.processor.filter import parse_episodes, check_episodes
import pytest


@pytest.mark.processor
def test_regex():
    # 单个
    assert check_episodes("1")
    assert check_episodes("99")
    assert check_episodes("-1")
    assert check_episodes("-99")
    assert check_episodes("$")
    assert not check_episodes("")
    assert not check_episodes(" ")
    assert not check_episodes("x")
    assert not check_episodes("- 1")
    assert not check_episodes("1$")

    # 组合
    assert check_episodes("1,2")
    assert check_episodes("1,-2,3,-4")
    assert not check_episodes("1, 2")
    assert not check_episodes("1,")

    # 范围
    assert check_episodes("1~3")
    assert check_episodes("1~-1")
    assert check_episodes("-2~-1")
    assert not check_episodes("1~2~3")

    # 范围 + 组合
    assert check_episodes("1~2,9~$")
    assert check_episodes("0~10,12~14,-2~$")

    # 起止省略语法糖
    assert check_episodes("~2,9~")
    assert check_episodes("9~,~2")
    assert check_episodes("~")


@pytest.mark.processor
def test_single():
    assert parse_episodes("1", 24) == [1]
    assert parse_episodes("11", 24) == [11]
    assert parse_episodes("-1", 24) == [24]
    assert parse_episodes("-10", 24) == [15]
    assert parse_episodes("$", 24) == [24]
    assert parse_episodes("25", 24) == []


@pytest.mark.processor
def test_compose():
    assert parse_episodes("1,2,4", 24) == [1, 2, 4]
    assert parse_episodes("11,14,15", 24) == [11, 14, 15]
    assert parse_episodes("11,14,25", 24) == [11, 14]
    assert parse_episodes("11,-1,$", 24) == [11, 24]
    assert parse_episodes("$,-10", 24) == [15, 24]


@pytest.mark.processor
def test_range():
    assert parse_episodes("1~4", 24) == [1, 2, 3, 4]
    assert parse_episodes("1~100", 6) == [1, 2, 3, 4, 5, 6]
    assert parse_episodes("4~10", 6) == [4, 5, 6]
    assert parse_episodes("2~-2", 6) == [2, 3, 4, 5]
    assert parse_episodes("2~$", 6) == [2, 3, 4, 5, 6]


@pytest.mark.processor
def test_range_and_compose():
    assert parse_episodes("1~4,6~8", 24) == [1, 2, 3, 4, 6, 7, 8]
    assert parse_episodes("1~4,2~6", 24) == [1, 2, 3, 4, 5, 6]
    assert parse_episodes("1~4,5~6", 24) == [1, 2, 3, 4, 5, 6]
    assert parse_episodes("1~4,5~6,8", 24) == [1, 2, 3, 4, 5, 6, 8]
    assert parse_episodes("3,5~7,12,17", 24) == [3, 5, 6, 7, 12, 17]
    assert parse_episodes("1~3,10,12~14,16,-4~$", 24) == [1, 2, 3, 10, 12, 13, 14, 16, 21, 22, 23, 24]


@pytest.mark.processor
def test_sugar():
    assert parse_episodes("~4,20~", 24) == parse_episodes("1~4,20~24", 24)
    assert parse_episodes("~4,20~$", 24) == parse_episodes("1~4,20~24", 24)
    assert parse_episodes("~", 24) == parse_episodes("1~24", 24)
