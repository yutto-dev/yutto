use std::io::Result;
fn main() -> Result<()> {
    let file_descriptors = protox::compile(
        ["proto/danmaku.proto", "proto/danmaku_view.proto"],
        ["proto/"],
    )
    .expect("Failed to compile proto file");
    prost_build::compile_fds(file_descriptors)?;
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=proto/danmaku.proto");
    Ok(())
}
