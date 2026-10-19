# NF 执行层快路（生成自 `nf daemon shell-init bash`）
# 用法：  eval "$(nf daemon shell-init bash)"        # 或写进 ~/.bashrc
# 卸载：  unset -f nf
# 注意（2026-09 实测缺陷）：解释器与脚本路径**必须加引号**——本机解释器路径是
# `C:\Program Files\Python311\python.exe`，不加引号时回退那行会被 bash 拆成命令 `C:\Program`，
# 于是守护不在（含默认 1 小时空闲自退之后）时 `nf <任何命令>` → **rc=127 + `C:Program: command not found`**。
# 语法检查抓不到这种错（它语法合法），所以判据必须是**行为级**的（见 test_launcher/test_daemon）。
nf() {
  case "${1:-}" in
    daemon|shell|terminal|serve|lsp|"") command "C:\Program Files\Python311\python.exe" "C:\Users\mon_7\Downloads\NarrativeForge-main/scripts/nf.py" "$@"; return $? ;;
  esac
  # 明文框是**逐行** argv：参数里含换行会被拆开、**静默改变参数个数**（实测：`help` 收到
  # `line1\nline2` 时只看到 `line1`）——这类命令一律不接快路，交 python 直跑
  # （JSON 框才支持任意字符；见 `_parse_request` 的说明）。
  local _nf_a="" _nf_nl=""
  for _nf_a in "$@"; do
    case "$_nf_a" in *$'\n'*) _nf_nl=1 ;; esac
  done
  if [ -n "$_nf_nl" ]; then command "C:\Program Files\Python311\python.exe" "C:\Users\mon_7\Downloads\NarrativeForge-main/scripts/nf.py" "$@"; return $?; fi
  local _state="${NARRATIVE_FORGE_HOME:-$HOME/.NinFenz}/daemon.json"
  local _s="" _rest="" _port="" _token=""
  if [ -f "$_state" ]; then
    IFS= read -r _s < "$_state" || _s=""
    case "$_s" in *'"port": '* ) ;; *) _s="" ;; esac
  fi
  if [ -n "$_s" ]; then
    _rest=${_s#*'"port": '}; _port=${_rest%%[!0-9]*}
    _rest=${_s#*'"token": "'}; _token=${_rest%%\"*}
  fi
  if [ -n "$_port" ] && [ -n "$_token" ] && { exec 9<>"/dev/tcp/127.0.0.1/$_port"; } 2>/dev/null; then
    printf 'NFREQ 1 %s\n%s\n%s\n' "$_token" "$PWD" "$#" >&9
    local _a=""
    for _a in "$@"; do printf '%s\n' "$_a" >&9; done
    local _code="" _olen="" _elen=""
    if IFS= read -r _code <&9 && IFS= read -r _olen <&9 && IFS= read -r _elen <&9; then
      case "$_code$_olen$_elen" in
        *[!0-9]*) : ;;
        *)
          local _o="" _e=""
          if [ "$_olen" -gt 0 ]; then LC_ALL=C IFS= read -r -d '' -n "$_olen" _o <&9 || true; printf '%s' "$_o"; fi
          if [ "$_elen" -gt 0 ]; then LC_ALL=C IFS= read -r -d '' -n "$_elen" _e <&9 || true; printf '%s' "$_e" >&2; fi
          exec 9<&- || true
          return "$_code"
          ;;
      esac
    fi
    exec 9<&- 2>/dev/null || true
  fi
  command "C:\Program Files\Python311\python.exe" "C:\Users\mon_7\Downloads\NarrativeForge-main/scripts/nf.py" "$@"
}
