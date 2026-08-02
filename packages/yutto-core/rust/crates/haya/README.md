# haya

`haya` is a bounded, resilient, multi-source asynchronous downloader core.

It downloads a known-size resource from equivalent exact-Range sources into a
contiguous sink. The core provides a fixed-page ordered window, bounded
lookahead, source cooldown, finite retries, recursive block splitting,
cancellation, and progress snapshots. HTTP transport support lives in the
separate `haya-http` crate.

The public API is experimental and may change between `0.0.x` releases.

## License

Licensed under either of the Apache License, Version 2.0 or the MIT license at
your option.
