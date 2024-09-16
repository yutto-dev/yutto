from __future__ import annotations

import argparse
import ast
from pathlib import Path


class VersionAnalyzer(ast.NodeVisitor):
    def __init__(self, literal_name: str):
        self.literal_name = literal_name
        self.version = None

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.targets[0], ast.Name) and node.targets[0].id == self.literal_name:
            if self.version is not None:
                raise ValueError(f"Multiply version assignment for {self.literal_name} found")
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                self.version = node.value.value


def cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, help="The file to read")
    parser.add_argument("--literal-name", type=str, default="VERSION", help="The literal name to search")
    return parser.parse_args()


def main():
    args = cli()
    with Path(args.file).open("r") as f:
        code = f.read()
    tree = ast.parse(code)
    analyzer = VersionAnalyzer(args.literal_name)
    analyzer.visit(tree)
    version = analyzer.version
    if version is None:
        raise ValueError(f"Version not found for {args.literal_name}")
    print(version)


if __name__ == "__main__":
    main()
