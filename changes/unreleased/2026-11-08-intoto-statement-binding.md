type: feat
surface: standards
note: in-toto Statement v1 从 protocol/RECEIPTS.json 纯派生的绑定判据收紧：Python 与 .NET 均校验 Statement 类型、HTTPS predicateType、subject 的下标顺序/name/SHA-256 逐项同源，以及 predicate count/root/algorithm/scope 同源；合法但错误的摘要、换序、类型或 predicate 元数据漂移均 fail-closed。该面仍明确只声明 unsigned Statement 形状，不宣称 DSSE 签名、外部验证器认证或 SLSA 等级。回滚：单 commit revert；导出字节形状不变，仅门禁判据变严。
