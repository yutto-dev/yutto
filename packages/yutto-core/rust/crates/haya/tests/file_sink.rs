use bytes::Bytes;
use haya::{
    CommitSink,
    file::{FileOpenMode, FileSink},
};

#[tokio::test]
async fn overwrites_and_appends_contiguously() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    tokio::fs::write(&path, b"old bytes")
        .await
        .expect("seed output");

    let sink = FileSink::open(&path, FileOpenMode::Overwrite)
        .await
        .expect("open sink");
    sink.append(0, Bytes::from_static(b"new"))
        .await
        .expect("append bytes");
    sink.close().await.expect("close sink");

    assert_eq!(tokio::fs::read(path).await.expect("read output"), b"new");
}

#[tokio::test]
async fn resumes_from_the_existing_contiguous_length() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    tokio::fs::write(&path, b"prefix")
        .await
        .expect("seed output");

    let sink = FileSink::open(&path, FileOpenMode::ResumeFromLength)
        .await
        .expect("open sink");
    assert_eq!(sink.committed_offset().await.expect("read offset"), 6);
    sink.append(6, Bytes::from_static(b"-suffix"))
        .await
        .expect("append bytes");
    sink.flush().await.expect("flush sink");

    assert_eq!(
        tokio::fs::read(path).await.expect("read output"),
        b"prefix-suffix"
    );
}

#[tokio::test]
async fn rejects_non_contiguous_writes_and_writes_after_close() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    let sink = FileSink::open(&path, FileOpenMode::Overwrite)
        .await
        .expect("open sink");

    assert!(sink.append(1, Bytes::from_static(b"gap")).await.is_err());
    sink.close().await.expect("close sink");
    assert!(sink.append(0, Bytes::from_static(b"late")).await.is_err());
}
