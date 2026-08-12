use bytes::Bytes;
use haya::{
    CommitBatch, CommitSink,
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
async fn appends_a_multi_chunk_batch_as_one_commit() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    let sink = FileSink::open(&path, FileOpenMode::Overwrite)
        .await
        .expect("open sink");

    sink.append_batch(
        CommitBatch::new(
            0,
            vec![
                Bytes::from_static(b"first-"),
                Bytes::from_static(b"second-"),
                Bytes::from_static(b"tail"),
            ],
        )
        .expect("valid batch"),
    )
    .await
    .expect("append batch");

    assert_eq!(sink.committed_offset().await.expect("offset"), 17);
    assert_eq!(
        tokio::fs::read(&path).await.expect("read output"),
        b"first-second-tail"
    );
}

#[tokio::test]
async fn resumes_with_a_non_aligned_multi_chunk_batch() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    tokio::fs::write(&path, b"prefix!")
        .await
        .expect("seed output");
    let sink = FileSink::open(&path, FileOpenMode::ResumeFromLength)
        .await
        .expect("open sink");

    sink.append_batch(
        CommitBatch::new(
            7,
            vec![Bytes::from_static(b"-middle"), Bytes::from_static(b"-tail")],
        )
        .expect("valid batch"),
    )
    .await
    .expect("append batch");
    sink.close().await.expect("close sink");

    assert_eq!(
        tokio::fs::read(&path).await.expect("read output"),
        b"prefix!-middle-tail"
    );
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

#[tokio::test]
async fn preserves_empty_append_behavior() {
    let directory = tempfile::tempdir().expect("temporary directory");
    let path = directory.path().join("output.bin");
    let sink = FileSink::open(&path, FileOpenMode::Overwrite)
        .await
        .expect("open sink");

    sink.append(0, Bytes::new()).await.expect("empty append");
    assert_eq!(sink.committed_offset().await.expect("offset"), 0);
    assert!(sink.append(1, Bytes::new()).await.is_err());
}
