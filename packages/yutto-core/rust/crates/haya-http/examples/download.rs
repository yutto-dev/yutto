use std::{env, sync::Arc};

use haya::{
    DownloadSpec, Downloader,
    file::{FileOpenMode, FileSink},
};
use haya_http::HttpRangeSource;
use reqwest::{Client, Url, header::HeaderMap};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut arguments = env::args_os().skip(1);
    let url = arguments.next().ok_or("usage: download URL OUTPUT SIZE")?;
    let output = arguments.next().ok_or("usage: download URL OUTPUT SIZE")?;
    let size = arguments.next().ok_or("usage: download URL OUTPUT SIZE")?;
    if arguments.next().is_some() {
        return Err("usage: download URL OUTPUT SIZE".into());
    }

    let url = Url::parse(url.to_str().ok_or("URL must be valid UTF-8")?)?;
    let size = size
        .to_str()
        .ok_or("SIZE must be valid UTF-8")?
        .parse::<u64>()?;
    let source = Arc::new(HttpRangeSource::new(
        Client::new(),
        url,
        HeaderMap::new(),
        size,
    ));
    let sink = Arc::new(FileSink::open(output, FileOpenMode::ResumeFromLength).await?);
    let report = Downloader::new(DownloadSpec::new(size), vec![source], sink)?
        .run()
        .await?;
    println!("downloaded {} bytes", report.committed_bytes);
    Ok(())
}
