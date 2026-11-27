//! CPython `random` 的复刻：**MT19937 + `seed(int)` + `getrandbits` + `sample`**。
//!
//! ## 为什么必须逐位复刻
//!
//! 真源 `pack_combo.breadth` 用 `random.Random(seed).sample(names, k)` 抽三元/四元/五元/六元样，
//! 而**抽到哪些组合直接进判据与 stats**（`triples_legal` / `failures` / `all_legal`）。
//! 抽样器差一位，结论就不同——这不是"看起来一样"，是要**同一个序列**。
//!
//! ## 复刻的三层（对照 CPython 3.11 的 `Lib/random.py` 与 `Modules/_randommodule.c`）
//!
//! 1. **`init_by_array`**：`seed(int)` 走它——把 `abs(n)` 按**32 位小端字**当 key；
//! 2. **`genrand_uint32`**：标准 MT19937（N=624 / M=397 / mag01=0x9908b0df）；
//! 3. **`_randbelow_with_getrandbits` + `sample`**：`k ≤ 32` 时 `getrandbits(k)` 取
//!    `genrand_uint32() >> (32 - k)`；`sample` 按 `n` 与 `setsize` 的大小走**两条不同分支**
//!    （选择池 / 选择集）。二者都会用到，故**两条都实现**。
//!
//! 验证在 `gen_pyrandom_cases.py`：与真源 `random.Random(seed)` 在同一批 (n, k) 上逐序列比对。

const N: usize = 624;
const M: usize = 397;
const MATRIX_A: u32 = 0x9908b0df;
const UPPER_MASK: u32 = 0x80000000;
const LOWER_MASK: u32 = 0x7fffffff;

/// CPython `random.Random` 的对应物。
pub struct PyRandom {
    mt: [u32; N],
    mti: usize,
}

impl PyRandom {
    /// 真源 `random.Random(seed)`（`seed` 为**非负整数**——本仓 `breadth` 的 `seed=20260923`）。
    ///
    /// CPython 对 int 种子取 `abs(n)` 的**小端 32 位字**为 key，再走 `init_by_array`。
    pub fn new(seed: u64) -> Self {
        let mut key: Vec<u32> = Vec::new();
        let mut v = seed;
        if v == 0 {
            key.push(0);
        } else {
            while v > 0 {
                key.push((v & 0xffff_ffff) as u32);
                v >>= 32;
            }
        }
        let mut r = PyRandom {
            mt: [0u32; N],
            mti: N + 1,
        };
        r.init_by_array(&key);
        r
    }

    fn init_genrand(&mut self, s: u32) {
        self.mt[0] = s;
        for i in 1..N {
            let prev = self.mt[i - 1];
            self.mt[i] = 1812433253u32
                .wrapping_mul(prev ^ (prev >> 30))
                .wrapping_add(i as u32);
        }
        self.mti = N;
    }

    fn init_by_array(&mut self, key: &[u32]) {
        self.init_genrand(19650218);
        let key_length = key.len();
        let mut i = 1usize;
        let mut j = 0usize;
        let mut k = if N > key_length { N } else { key_length };
        while k > 0 {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
            if j >= key_length {
                j = 0;
            }
            k -= 1;
        }
        let mut k = N - 1;
        while k > 0 {
            let prev = self.mt[i - 1];
            self.mt[i] = (self.mt[i] ^ (prev ^ (prev >> 30)).wrapping_mul(1566083941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                self.mt[0] = self.mt[N - 1];
                i = 1;
            }
            k -= 1;
        }
        self.mt[0] = 0x80000000;
    }

    /// CPython `genrand_uint32`。
    pub fn genrand_uint32(&mut self) -> u32 {
        if self.mti >= N {
            for kk in 0..(N - M) {
                let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
                self.mt[kk] = self.mt[kk + M] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            for kk in (N - M)..(N - 1) {
                let y = (self.mt[kk] & UPPER_MASK) | (self.mt[kk + 1] & LOWER_MASK);
                self.mt[kk] =
                    self.mt[kk - (N - M)] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            }
            let y = (self.mt[N - 1] & UPPER_MASK) | (self.mt[0] & LOWER_MASK);
            self.mt[N - 1] = self.mt[M - 1] ^ (y >> 1) ^ if y & 1 != 0 { MATRIX_A } else { 0 };
            self.mti = 0;
        }
        let mut y = self.mt[self.mti];
        self.mti += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^= y >> 18;
        y
    }

    /// CPython `getrandbits(k)`（**只用 k ≤ 32 这一支**——本仓 `sample` 的 k ≤ 7）。
    pub fn getrandbits(&mut self, k: u32) -> u32 {
        if k == 0 {
            return 0;
        }
        if k <= 32 {
            return self.genrand_uint32() >> (32 - k);
        }
        // 真源在 k > 32 时拼多个 32 位字；本仓用不到 ⇒ fail-closed，不近似
        // audit: panic-fail-closed —— 越出已复刻子集必须炸，静默近似会破坏逐位对账。
        panic!("getrandbits(k>32) 不在本线复刻的子集内（真源此处亦未用到）");
    }

    /// CPython `_randbelow_with_getrandbits`。
    pub fn randbelow(&mut self, n: u64) -> u64 {
        if n == 0 {
            return 0;
        }
        let k = 64 - n.leading_zeros(); // n.bit_length()
        loop {
            let r = self.getrandbits(k) as u64;
            if r < n {
                return r;
            }
        }
    }

    /// CPython `random.sample(population, k)`（**两条分支都实现**）。
    ///
    /// 全部样本的取出顺序即返回值顺序（真源随后会 `sorted(...)` 去重，但**抽取本身**要逐位一致）。
    pub fn sample(&mut self, population: &[String], k: usize) -> Vec<String> {
        let n = population.len();
        assert!(k <= n, "sample 的 k 不得超过总体大小");
        let mut result: Vec<Option<String>> = vec![None; k];
        // setsize = 21; if k > 5: setsize += 4 ** ceil(log(k*3, 4))
        let mut setsize = 21f64;
        if k > 5 {
            let lg = ((k as f64) * 3.0).log(4.0).ceil();
            setsize += 4f64.powf(lg);
        }
        if (n as f64) <= setsize {
            let mut pool: Vec<String> = population.to_vec();
            for i in 0..k {
                let j = self.randbelow((n - i) as u64) as usize;
                result[i] = Some(pool[j].clone());
                pool[j] = pool[n - i - 1].clone();
            }
        } else {
            let mut selected: std::collections::BTreeSet<u64> = std::collections::BTreeSet::new();
            for slot in result.iter_mut().take(k) {
                let mut j = self.randbelow(n as u64);
                while selected.contains(&j) {
                    j = self.randbelow(n as u64);
                }
                selected.insert(j);
                *slot = Some(population[j as usize].clone());
            }
        }
        result.into_iter().map(|x| x.unwrap()).collect()
    }
}

#[cfg(test)]
#[path = "generated/pyrandom_gen.rs"]
mod pyrandom_gen;
