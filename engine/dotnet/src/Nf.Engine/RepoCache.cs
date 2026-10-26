namespace Nf.Engine;

/// <summary>
/// 进程级仓库画像缓存（等价 Python <c>pack_combo._CACHE</c>）。
///
/// 为什么必要（实测）：17 条证书逐条解算 = 17 次组合，若每次都重读 111 个 `protocol.yaml`
/// 与 235 个模块文档，实测 3.18 s，而 Python 侧（带缓存）0.67 s。广度证明要跑数千次组合，
/// 无缓存的代价是 O(N²·files)。本类把「解析」与「求解」分开：解析一次，求解复用。
/// </summary>
public static class RepoCache
{
    public sealed record Entry(
        SortedDictionary<string, PackProfiles.Profile> Profiles,
        IReadOnlyDictionary<string, ModuleContracts.Contract> Contracts,
        IReadOnlyDictionary<string, ModuleContracts.CoreContract> CoreContracts);

    private static readonly object Gate = new();
    private static readonly Dictionary<string, Entry> Cache = new(StringComparer.Ordinal);

    /// <summary>
    /// Git worktrees store <c>.git</c> as a pointer file rather than a directory.
    /// Both forms are a working tree; treating the file form as an exported
    /// snapshot incorrectly enables immutable-golden digest assertions.
    /// </summary>
    public static bool IsWorkingTree(string root)
    {
        var git = Path.Combine(root, ".git");
        return Directory.Exists(git) || File.Exists(git);
    }

    public static Entry For(string root)
    {
        var key = Path.GetFullPath(root);
        lock (Gate)
        {
            if (Cache.TryGetValue(key, out var cached)) return cached;
            var extraction = ModuleContracts.Community(root);
            var core = ModuleContracts.Core(root);
            var profiles = PackProfiles.BuildUncached(root, extraction.RecordsByKey);
            var entry = new Entry(profiles, extraction.RecordsByKey, core);
            Cache[key] = entry;
            return entry;
        }
    }

    public static void Clear()
    {
        lock (Gate) Cache.Clear();
    }
}
