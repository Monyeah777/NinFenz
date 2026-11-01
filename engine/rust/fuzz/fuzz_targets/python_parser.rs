#![no_main]

use libfuzzer_sys::fuzz_target;
use rustpython_parser::{parse, Mode};

fuzz_target!(|data: &[u8]| {
    if let Ok(source) = std::str::from_utf8(data) {
        let _ = parse(source, Mode::Module, "<fuzz>");
    }
});
