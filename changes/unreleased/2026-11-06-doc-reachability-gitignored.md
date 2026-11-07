type: fix
surface: docs
note: 文档路径判据放行 gitignored 构建产物（修快照模式假红）。test_doc_reachability 在「路径缺失」分支加 `git check-ignore` 权威判定：被 .gitignore 覆盖的路径（如 engine/dotnet/dist/ 构建产物）按设计不入库，fresh clone/HEAD 干净 worktree 不在场是合法状态，不再判红；非 ignored 的缺失仍照判（既有边界测试不变）。为什么：--snapshot 发布结论在 HEAD 的干净 worktree 里跑，engine/dotnet/dist 缺席导致 8 片全红（实测 release-snapshot.log）。判据：test_doc_reachability 17 项在主树与干净 worktree 双跑全绿；新增 1 条判据（gitignored 放行 + 裸目录名/带斜杠两种写法）。
