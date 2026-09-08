// rust_core/tests/purity_scan.rs
//
// Python tarafındaki test_resolver_module_has_no_forbidden_imports ile
// SİMETRİK: token_compressor.rs'in yasaklı bağımlılıklara (dosya/ağ/
// CanonicalMemory kavramları) DOKUNMADIĞINI derleme sonrası değil,
// kaynak metni üzerinden statik olarak doğrular.

use std::fs;

#[test]
fn token_compressor_has_no_forbidden_deps() {
    let source = fs::read_to_string("src/token_compressor.rs")
        .expect("token_compressor.rs okunamadı");

    let forbidden_tokens = [
        "std::fs",
        "std::net",
        "reqwest",
        "tokio::net",
        "canonical_memory",
        "hindsight_memory",
        "task_executor",
        "CanonicalMemory",
        "HindsightMemory",
    ];

    for token in forbidden_tokens {
        assert!(
            !source.contains(token),
            "YASAKLI BAĞIMLILIK BULUNDU: '{}' — token_compressor.rs saf kalmalı",
            token
        );
    }
}
