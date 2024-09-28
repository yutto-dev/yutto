use tracing::Level;

pub fn enable_tracing() {
    let collector = tracing_subscriber::fmt()
        .with_max_level(Level::TRACE)
        .finish();

    tracing::subscriber::set_global_default(collector).expect("setting tracing default failed");
}
