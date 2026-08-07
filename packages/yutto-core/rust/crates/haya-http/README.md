# haya-http

`haya-http` provides the reqwest-based HTTP Range source adapter for `haya`.

It sends exact Range requests, validates partial responses, streams response bytes, and accepts an externally configured `reqwest::Client` so the caller retains control of proxies, TLS, cookies, headers, and connection pools.

The injected client's default headers must not contain `If-Range`; the adapter deliberately strips any per-source `If-Range` value.

The public API is experimental and may change between `0.0.x` releases.

## License

Licensed under either of the Apache License, Version 2.0 or the MIT license at your option.
