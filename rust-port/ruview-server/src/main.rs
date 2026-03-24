use std::sync::Arc;

use ruview_server::{create_router, AppState};

#[tokio::main]
async fn main() {
    let state = Arc::new(AppState::new());

    println!("RuView server listening on 0.0.0.0:8001");

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8001")
        .await
        .unwrap();
    axum::serve(listener, create_router(state)).await.unwrap();
}
