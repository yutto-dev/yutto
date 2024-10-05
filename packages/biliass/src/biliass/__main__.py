from __future__ import annotations

import argparse
import sys

from biliass import convert_to_ass
from biliass.__version__ import VERSION as biliass_version
from biliass._core import BlockOptions


def main():
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    parser = argparse.ArgumentParser(description="bilibili ASS Danmaku converter", prog="biliass")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {biliass_version}")
    parser.add_argument("-o", "--output", metavar="OUTPUT", help="Output file")
    parser.add_argument(
        "-s",
        "--size",
        metavar="WIDTHxHEIGHT",
        required=True,
        help="Stage size in pixels",
    )
    parser.add_argument(
        "-fn",
        "--font",
        metavar="FONT",
        help="Specify font face [default: sans-serif]",
        default="sans-serif",
    )
    parser.add_argument(
        "-fs",
        "--fontsize",
        metavar="SIZE",
        help="Default font size [default: 25]",
        type=float,
        default=25.0,
    )
    parser.add_argument("-a", "--alpha", metavar="ALPHA", help="Text opacity", type=float, default=1.0)
    parser.add_argument(
        "-dm",
        "--duration-marquee",
        metavar="SECONDS",
        help="Duration of scrolling comment display [default: 5]",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "-ds",
        "--duration-still",
        metavar="SECONDS",
        help="Duration of still comment display [default: 5]",
        type=float,
        default=5.0,
    )
    parser.add_argument("--block-top", action="store_true", help="Block top comments")
    parser.add_argument("--block-bottom", action="store_true", help="Block bottom comments")
    parser.add_argument("--block-scroll", action="store_true", help="Block scrolling comments")
    parser.add_argument("--block-reverse", action="store_true", help="Block reverse comments")
    parser.add_argument("--block-fixed", action="store_true", help="Block fixed comments (top, bottom)")
    parser.add_argument("--block-special", action="store_true", help="Block special comments")
    parser.add_argument("--block-colorful", action="store_true", help="Block colorful comments")
    parser.add_argument(
        "--block-keyword-patterns",
        default=None,
        help="Block comments that match the keyword pattern, separated by commas",
    )
    parser.add_argument(
        "--display-region-ratio",
        help="Ratio of the display region to the stage height [default: 1.0]",
        type=float,
        default=1.0,
    )
    parser.add_argument(
        "--skip-reduce",
        action="store_true",
        help="Do not reduce the amount of comments if stage is full",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["xml", "protobuf"],
        default="xml",
        help="Input danmaku format (xml or protobuf)",
    )
    parser.add_argument("file", metavar="FILE", nargs="+", help="Comment file to be processed")
    args = parser.parse_args()
    try:
        width, height = str(args.size).split("x", 1)
        width = int(width)
        height = int(height)
    except ValueError:
        raise ValueError(f"Invalid stage size: {args.size!r}") from None

    inputs: list[str | bytes] = []
    for file in args.file:
        try:
            with open(file, "r" if args.format == "xml" else "rb") as f:  # noqa: PTH123
                inputs.append(f.read())
        except UnicodeDecodeError:
            print(f"Failed to decode file {file}, if it is a protobuf file, please use `-f protobuf`")
            sys.exit(1)

    if args.output:
        fout = open(args.output, "w", encoding="utf-8-sig", errors="replace", newline="\r\n")  # noqa: PTH123
    else:
        fout = sys.stdout
    output = convert_to_ass(
        inputs,
        width,
        height,
        args.format,
        args.display_region_ratio,
        args.font,
        args.fontsize,
        args.alpha,
        args.duration_marquee,
        args.duration_still,
        parse_block_options(args),
        not args.skip_reduce,
    )
    fout.write(output)
    fout.close()


def parse_block_options(args: argparse.Namespace) -> BlockOptions:
    return BlockOptions(
        block_top=args.block_top or args.block_fixed,
        block_bottom=args.block_bottom or args.block_fixed,
        block_scroll=args.block_scroll,
        block_reverse=args.block_reverse,
        block_special=args.block_special,
        block_colorful=args.block_colorful,
        block_keyword_patterns=(
            [pattern.strip() for pattern in args.block_keyword_patterns.split(",")]
            if args.block_keyword_patterns
            else []
        ),
    )


if __name__ == "__main__":
    main()
