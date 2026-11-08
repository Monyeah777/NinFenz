type: feat
surface: standards
note: 新增 DSSE v1.0.2 signed-envelope 可消费面：严格 PAE、标准/URL-safe Base64 双解码、必需字段、未知字段容忍、keyid 仅作提示、HMAC-SHA256 单/多签名与唯一密钥阈值验证；验签返回原始 payload bytes，禁止重解析替换。Python 与 .NET 使用同一算法和官方向量；边界明确 HMAC 不等于第三方身份证明，不宣称 Sigstore/SLSA 等级。回滚：单 commit revert，既有 attest/evidence 行为不变。
