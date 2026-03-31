# AGENTS.md

Repository instructions for automated agents contributing to `yutto`.

## Scope

- Keep changes focused and avoid unrelated refactors in the same PR.
- Prefer a clean topic branch. If a checkout already contains unrelated changes, use a separate git worktree instead of reusing the dirty tree.
- When in doubt, follow `CONTRIBUTING.md`, `justfile`, and the relevant workflow file.

## Repository map

- `src/yutto/`: main Python CLI implementation.
- `tests/`: pytest suites for API, processor, e2e, and biliass-related coverage.
- `packages/biliass/`: Rust-backed workspace package used by `yutto`.
- `docs/`: VitePress documentation site.
- `scripts/`: project maintenance scripts.
- `schemas/`: generated schemas and related assets.
- `tests/test_biliass/test_corpus/`: git submodule with external corpus data. Do not edit it or move its pointer unless the task explicitly requires corpus updates.

## Bootstrap

- Baseline tools: `uv`, `just`, Python 3.10, and FFmpeg.
- If you touch `packages/biliass` or run a full workspace install from source, also install stable Rust with `clippy` and `rustfmt`.
- If you touch docs, use the Node/pnpm setup shown in `.github/workflows/vitepress-deploy.yml`.
- In GitHub Copilot environments, start from `.github/workflows/copilot-setup-steps.yml`.

## Common commands

```bash
just install
just run -- -h
just fmt
just lint
just test
just ci-install 3.10
just ci-test 3.10
just ci-e2e-test 3.10
just build
just docs-setup
just docs-build
```

For biliass Rust changes, also run:

```bash
cd packages/biliass/rust
cargo fmt --all
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

Use `just run -- ...` or `uv run python -m yutto ...` for local CLI testing. Do not use a globally installed `yutto` binary when you mean to test the local checkout.

## Commit and PR conventions

- Prefer commit titles and PR titles in the `<gitmoji> <type>: <subject>` style described in `CONTRIBUTING.md`.
- Reuse the type vocabulary implied by `.github/PULL_REQUEST_TEMPLATE.md` and keep the subject focused on the actual repo change.
- Fill in the PR template sections and check the relevant type boxes instead of replacing the template with free-form text.
- If a commit is created with help from a coding agent, include the relevant `Co-authored-by` trailer(s) in the commit message. Common examples:
  - `Co-authored-by: Codex <codex@openai.com>`
  - `Co-authored-by: Claude <noreply@anthropic.com>`
  - `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

## Validation before submission

- After each code change round, run `just fmt` and `just lint` before handing work back, then run the narrowest relevant test target for the files you changed.
- Run the narrowest relevant checks for the files you changed.
- For Python source changes, run `just fmt`, `just lint`, and the relevant pytest target(s).
- For workflow changes, keep action versions, step naming, and structure aligned with the existing workflows in `.github/workflows/`.
- For docs changes, run `just docs-build` or the equivalent VitePress checks.
- For `packages/biliass` changes, run the Rust checks above and any relevant Python integration checks.
- Do not update `uv.lock` unless dependency definitions changed.
- Do not commit build artifacts, downloaded media, local virtual environments, or other machine-specific outputs.

## Boundaries and repo-specific notes

- Avoid changing release automation, version numbers, or publishing flows unless the task explicitly asks for release work.
- Preserve existing user-facing Chinese copy unless the task explicitly calls for wording updates.
- Reuse existing `justfile` tasks and workflow patterns instead of inventing one-off scripts.
