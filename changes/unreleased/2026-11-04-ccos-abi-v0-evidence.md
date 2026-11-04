type: fix
surface: ccos
note: 证据线 fail-closed 加固（攻击矩阵 25→29）：chain 段改必填且自洽（缺段/空链头/计数不符一律 invalid——缺证据不等于证据成立）、包内吊销表坏件与 schema 不符不再折成「无吊销」（坏件冒充合格），零依赖单文件复验器同步同一口径并补双实现一致性判据；另修全量档分片暴露的原子写纪律、JSON 面登记、json_doc 收敛、Rust 快线回执同步与 check12 权重；分片 0/8 与 4/8 实测 rc=0
