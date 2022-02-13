def gen_priority_sequence(choice: int, num_choices: int) -> list[int]:
    """根据默认先降后升的机制生成序列

    值得注意的是，默认的优先级序列应当满足从左向右兼容性逐渐提高，以保证默认策略不会影响兼容性
    - 在清晰度中，应当从左向右清晰度降低
    - 在编码方式中，应当从左向右兼容性提高，压缩率降低

    Args:
        choice (int): 是当前选择的目标索引
        num_choices (int): 是可选择目标数量

    """

    assert choice >= 0 and choice < num_choices
    default_policy = list(range(num_choices))

    return default_policy[choice:] + list(reversed(default_policy[:choice]))
