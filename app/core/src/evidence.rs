//! nf-evidence/1：证据随包、Ed25519 签名、离线验证。
//! 签名覆盖除 signature 外的全部字段（canonical JSON），不依赖网络/时间戳/CA。

use crate::canonical::{canonical_bytes, digest_value, sha256_hex};
use crate::error::{CoreError, OpOutcome};
use crate::fsutil;
use crate::ops::{opt_str, req_value, usage};
use crate::report::Report;
use crate::sdir;
use crate::schema::validate;
use crate::zipsec;
use ed25519_compact::{KeyPair, PublicKey, Seed, Signature};
use serde_json::{json, Map, Value};

mod crypto_create;
mod pack_verify;

pub use crypto_create::*;
pub use pack_verify::*;
