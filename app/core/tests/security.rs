//! 解析硬化：zip slip / bomb / symlink / 嵌套 / 重名；YAML 别名；JSON 深度。

#[path = "common/mod.rs"]
mod common;

use common::*;
use nf_app_core::yaml;
use serde_json::json;
use std::io::{Cursor, Write};
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, ZipWriter};

fn build_zip(entries: &[(&str, &[u8])]) -> Vec<u8> {
    let mut cursor = Cursor::new(Vec::new());
    {
        let mut writer = ZipWriter::new(&mut cursor);
        for (name, data) in entries {
            writer.start_file(*name, SimpleFileOptions::default()).unwrap();
            writer.write_all(data).unwrap();
        }
        writer.finish().unwrap();
    }
    cursor.into_inner()
}

fn replace_all(hay: &mut [u8], from: &[u8], to: &[u8]) {
    assert_eq!(from.len(), to.len());
    let mut i = 0;
    while i + from.len() <= hay.len() {
        if &hay[i..i + from.len()] == from {
            hay[i..i + from.len()].copy_from_slice(to);
            i += from.len();
        } else {
            i += 1;
        }
    }
}

#[test]
fn zip_slip_rejected() {
    let mut bytes = build_zip(&[("aa/evil.txt", b"x")]);
    replace_all(&mut bytes, b"aa/evil.txt", b"../evil.txt");
    let env = dispatch("import-sniff", &json!({"name": "x.zip", "bytes_path": write_bytes_to_tmp(&bytes)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-001");
}

fn write_bytes_to_tmp(bytes: &[u8]) -> String {
    let dir = tmpdir("sec_zip");
    let p = dir.join("payload.zip");
    std::fs::write(&p, bytes).unwrap();
    pstr(&p)
}

#[test]
fn zip_bomb_ratio_rejected() {
    let payload = vec![0u8; 2 * 1024 * 1024];
    let mut cursor = Cursor::new(Vec::new());
    {
        let mut writer = ZipWriter::new(&mut cursor);
        writer
            .start_file(
                "bomb.txt",
                SimpleFileOptions::default().compression_method(CompressionMethod::Deflated),
            )
            .unwrap();
        writer.write_all(&payload).unwrap();
        writer.finish().unwrap();
    }
    let bytes = cursor.into_inner();
    let env = dispatch("import-sniff", &json!({"name": "bomb.zip", "bytes_path": write_bytes_to_tmp(&bytes)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-003");
}

#[test]
fn zip_symlink_rejected() {
    let mut cursor = Cursor::new(Vec::new());
    {
        let mut writer = ZipWriter::new(&mut cursor);
        writer
            .add_symlink("link", "target", SimpleFileOptions::default())
            .unwrap();
        writer.finish().unwrap();
    }
    let bytes = cursor.into_inner();
    let env = dispatch("import-sniff", &json!({"name": "sym.zip", "bytes_path": write_bytes_to_tmp(&bytes)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-002");
}

#[test]
fn zip_duplicate_entry_rejected() {
    // zip crate 写入器自己拒重名；改字节把 b.txt 改成 a.txt 造出重名归档。
    let mut bytes = build_zip(&[("a.txt", b"1"), ("b.txt", b"2")]);
    replace_all(&mut bytes, b"b.txt", b"a.txt");
    let env = dispatch("import-sniff", &json!({"name": "dup.zip", "bytes_path": write_bytes_to_tmp(&bytes)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-PCK-003");
}

#[test]
fn zip_nested_rejected() {
    let inner = build_zip(&[("a.txt", b"1")]);
    let bytes = build_zip(&[("inner.zip", &inner)]);
    let env = dispatch("import-sniff", &json!({"name": "nested.zip", "bytes_path": write_bytes_to_tmp(&bytes)}));
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-003");
}

#[test]
fn yaml_alias_rejected_by_parser() {
    let err = yaml::parse("a: &anchor value\nb: *anchor\n").unwrap_err();
    assert_eq!(err.code, "NF-SEC-004");
}

#[test]
fn yaml_merge_key_rejected() {
    let err = yaml::parse("a: 1\n<<: *base\n").unwrap_err();
    assert_eq!(err.code, "NF-SEC-004");
}

#[test]
fn json_depth_limit_via_cli() {
    let mut s = String::from("{\"value\":");
    for _ in 0..70 {
        s.push('[');
    }
    for _ in 0..70 {
        s.push(']');
    }
    s.push('}');
    let env = nf_app_core::cli::run("canonical", s.as_bytes());
    assert_eq!(env.exit, 3);
    assert_eq!(env.error.as_ref().unwrap()["code"], "NF-SEC-003");
}