namespace Nf.Engine;

/// <summary>
/// check32 四件子扫描器（world_slots / instruction_step_audit / payload_registry / payload_consumer）的
/// **金标向量**——每条 = (合成/真仓输入文件集, **真源导出的 (issues, stats)**)，机械导出（导出件
/// <c>_aux_golden.cs.txt</c> 留档）。真仓那四条 = 真材料（引擎在真仓上跑出的结果须与真源逐字段一致）；
/// 合成那十条 = 覆盖各判据的 FAIL 分支与边界（缺件 / 非法 kind / 未锚定路径段 / 未知子命令 /
/// 缺脚本 / 缺路径 / 死注册 / 漏登）。
/// </summary>
public static partial class AuxGolden
{
    /// <summary>`probes/_fixtures/_aux_golden.json`（四件 check32 子扫描器的输入文件集 + 真源导出期望）。机械导出。</summary>
    public const string GoldenJson = GoldenJsonPartA + GoldenJsonPartB + GoldenJsonPartC;

    private const string GoldenJsonPartA = @"[
 {
  ""expected"": {
   ""issues"": [],
   ""stats"": {
    ""arrays"": 3,
    ""slots"": 10
   }
  },
  ""files"": {},
  ""name"": ""world_slots"",
  ""scanner"": ""world_slots""
 },
 {
  ""expected"": {
   ""issues"": [],
   ""stats"": {
    ""docs"": 5,
    ""steps"": 9
   }
  },
  ""files"": {},
  ""name"": ""instruction_step_audit"",
  ""scanner"": ""instruction_step_audit""
 },
 {
  ""expected"": {
   ""issues"": [],
   ""stats"": {
    ""declared"": 443,
    ""pending"": 0,
    ""registered"": 443,
    ""used"": 443
   }
  },
  ""files"": {},
  ""name"": ""payload_registry"",
  ""scanner"": ""payload_registry""
 },
 {
  ""expected"": {
   ""issues"": [],
   ""stats"": {
    ""consumer_map"": {
     ""a01_report_conflict"": [
      ""大语言模型:M01""
     ],
     ""a01_report_ready"": [
      ""大语言模型:M01""
     ],
     ""a01_spec_conflict"": [
      ""大语言模型:M02""
     ],
     ""a01_spec_ready"": [
      ""大语言模型:M02""
     ],
     ""a02_report_conflict"": [
      ""多模态大模型:M01""
     ],
     ""a02_report_ready"": [
      ""多模态大模型:M01""
     ],
     ""a02_spec_conflict"": [
      ""多模态大模型:M02""
     ],
     ""a02_spec_ready"": [
      ""多模态大模型:M02""
     ],
     ""a03_report_conflict"": [
      ""视觉模型:M01""
     ],
     ""a03_report_ready"": [
      ""视觉模型:M01""
     ],
     ""a03_spec_conflict"": [
      ""视觉模型:M02""
     ],
     ""a03_spec_ready"": [
      ""视觉模型:M02""
     ],
     ""a04_report_conflict"": [
      ""语音识别与合成:M01""
     ],
     ""a04_report_ready"": [
      ""语音识别与合成:M01""
     ],
     ""a04_spec_conflict"": [
      ""语音识别与合成:M02""
     ],
     ""a04_spec_ready"": [
      ""语音识别与合成:M02""
     ],
     ""a05_report_conflict"": [
      ""音频与音乐生成:M01""
     ],
     ""a05_report_ready"": [
      ""音频与音乐生成:M01""
     ],
     ""a05_spec_conflict"": [
      ""音频与音乐生成:M02""
     ],
     ""a05_spec_ready"": [
      ""音频与音乐生成:M02""
     ],
     ""a06_report_conflict"": [
      ""视频生成与理解:M01""
     ],
     ""a06_report_ready"": [
      ""视频生成与理解:M01""
     ],
     ""a06_spec_conflict"": [
      ""视频生成与理解:M02""
     ],
     ""a06_spec_ready"": [
      ""视频生成与理解:M02""
     ],
     ""a07_report_conflict"": [
      ""图像生成与编辑:M01""
     ],
     ""a07_report_ready"": [
      ""图像生成与编辑:M01""
     ],
     ""a07_spec_conflict"": [
      ""图像生成与编辑:M02""
     ],
     ""a07_spec_ready"": [
      ""图像生成与编辑:M02""
     ],
     ""a08_report_conflict"": [
      ""三维与世界模型:M01""
     ],
     ""a08_report_ready"": [
      ""三维与世界模型:M01""
     ],
     ""a08_spec_conflict"": [
      ""三维与世界模型:M02""
     ],
     ""a08_spec_ready"": [
      ""三维与世界模型:M02""
     ],
     ""a09_report_conflict"": [
      ""代码大模型:M01""
     ],
     ""a09_report_ready"": [
      ""代码大模型:M01""
     ],
     ""a09_spec_conflict"": [
      ""代码大模型:M02""
     ],
     ""a09_spec_ready"": [
      ""代码大模型:M02""
     ],
     ""a10_report_conflict"": [
      ""数学与形式化推理:M01""
     ],
     ""a10_report_ready"": [
      ""数学与形式化推理:M01""
     ],
     ""a10_spec_conflict"": [
      ""数学与形式化推理:M02""
     ],
     ""a10_spec_ready"": [
      ""数学与形式化推理:M02""
     ],
     ""a11_report_conflict"": [
      ""嵌入与检索表示:M01""
     ],
     ""a11_report_ready"": [
      ""嵌入与检索表示:M01""
     ],
     ""a11_spec_conflict"": [
      ""嵌入与检索表示:M02""
     ],
     ""a11_spec_ready"": [
      ""嵌入与检索表示:M02""
     ],
     ""a12_report_conflict"": [
      ""强化学习与决策:M01""
     ],
     ""a12_report_ready"": [
      ""强化学习与决策:M01""
     ],
     ""a12_spec_conflict"": [
      ""强化学习与决策:M02""
     ],
     ""a12_spec_ready"": [
      ""强化学习与决策:M02""
     ],
     ""a13_report_conflict"": [
      ""具身智能与机器人:M01""
     ],
     ""a13_report_ready"": [
      ""具身智能与机器人:M01""
     ],
     ""a13_spec_conflict"": [
      ""具身智能与机器人:M02""
     ],
     ""a13_spec_ready"": [
      ""具身智能与机器人:M02""
     ],
     ""a14_report_conflict"": [
      ""端侧与边缘小模型:M01""
     ],
     ""a14_report_ready"": [
      ""端侧与边缘小模型:M01""
     ],
     ""a14_spec_conflict"": [
      ""端侧与边缘小模型:M02""
     ],
     ""a14_spec_ready"": [
      ""端侧与边缘小模型:M02""
     ],
     ""b01_report_conflict"": [
      ""文本生成与创作:M01""
     ],
     ""b01_report_ready"": [
      ""文本生成与创作:M01""
     ],
     ""b01_spec_conflict"": [
      ""文本生成与创作:M02""
     ],
     ""b01_spec_ready"": [
      ""文本生成与创作:M02""
     ],
     ""b02_report_conflict"": [
      ""摘要与信息压缩:M01""
     ],
     ""b02_report_ready"": [
      ""摘要与信息压缩:M01""
     ],
     ""b02_spec_conflict"": [
      ""摘要与信息压缩:M02""
     ],
     ""b02_spec_ready"": [
      ""摘要与信息压缩:M02""
     ],
     ""b03_report_conflict"": [
      ""机器翻译与本地化:M01""
     ],
     ""b03_report_ready"": [
      ""机器翻译与本地化:M01""
     ],
     ""b03_spec_conflict"": [
      ""机器翻译与本地化:M02""
     ],
     ""b03_spec_ready"": [
      ""机器翻译与本地化:M02""
     ],
     ""b04_report_conflict"": [
      ""分类与情感分析:M01""
     ],
     ""b04_report_ready"": [
      ""分类与情感分析:M01""
     ],
     ""b04_spec_conflict"": [
      ""分类与情感分析:M02""
     ],
     ""b04_spec_ready"": [
      ""分类与情感分析:M02""
     ],
     ""b05_report_conflict"": [
      ""信息抽取与结构化:M01""
     ],
     ""b05_report_ready"": [
      ""信息抽取与结构化:M01""
     ],
     ""b05_spec_conflict"": [
      ""信息抽取与结构化:M02""
     ],
     ""b05_spec_ready"": [
      ""信息抽取与结构化:M02""
     ],
     ""b06_report_conflict"": [
      ""知识问答与检索增强:M01""
     ],
     ""b06_report_ready"": [
      ""知识问答与检索增强:M01""
     ],
     ""b06_spec_conflict"": [
      ""知识问答与检索增强:M02""
     ],
     ""b06_spec_ready"": [
      ""知识问答与检索增强:M02""
     ],
     ""b07_report_conflict"": [
      ""多轮对话与角色扮演:M01""
     ],
     ""b07_report_ready"": [
      ""多轮对话与角色扮演:M01""
     ],
     ""b07_spec_conflict"": [
      ""多轮对话与角色扮演:M02""
     ],
     ""b07_spec_ready"": [
      ""多轮对话与角色扮演:M02""
     ],
     ""b08_report_conflict"": [
      ""代码生成与补全:M01""
     ],
     ""b08_report_ready"": [
      ""代码生成与补全:M01""
     ],
     ""b08_spec_conflict"": [
      ""代码生成与补全:M02""
     ],
     ""b08_spec_ready"": [
      ""代码生成与补全:M02""
     ],
     ""b09_report_conflict"": [
      ""代码审查与缺陷检测:M01""
     ],
     ""b09_report_ready"": [
      ""代码审查与缺陷检测:M01""
     ],
     ""b09_spec_conflict"": [
      ""代码审查与缺陷检测:M02""
     ],
     ""b09_spec_ready"": [
      ""代码审查与缺陷检测:M02""
     ],
     ""b10_report_conflict"": [
      ""测试与用例生成:M01""
     ],
     ""b10_report_ready"": [
      ""测试与用例生成:M01""
     ],
     ""b10_spec_conflict"": [
      ""测试与用例生成:M02""
     ],
     ""b10_spec_ready"": [
      ""测试与用例生成:M02""
     ],
     ""b11_report_conflict"": [
      ""数据分析与表格理解:M01""
     ],
     ""b11_report_ready"": [
      ""数据分析与表格理解:M01""
     ],
     ""b11_spec_conflict"": [
      ""数据分析与表格理解:M02""
     ],
     ""b11_spec_ready"": [
      ""数据分析与表格理解:M02""
     ],
     ""b12_report_conflict"": [
      ""文档解析与版面理解:M01""
     ],
     ""b12_report_ready"": [
      ""文档解析与版面理解:M01""
     ],
     ""b12_spec_conflict"": [
      ""文档解析与版面理解:M02""
     ],
     ""b12_spec_ready"": [
      ""文档解析与版面理解:M02""
     ],
     ""b13_report_conflict"": [
      ""语音转写与会议记录:M01""
     ],
     ""b13_report_ready"": [
      ""语音转写与会议记录:M01""
     ],
     ""b13_spec_conflict"": [
      ""语音转写与会议记录:M02""
     ],
     ""b13_spec_ready"": [
      ""语音转写与会议记录:M02""
     ],
     ""b14_report_conflict"": [
      ""语音合成与配音:M01""
     ],
     ""b14_report_ready"": [
      ""语音合成与配音:M01""
     ],
     ""b14_spec_conflict"": [
      ""语音合成与配音:M02""
     ],
     ""b14_spec_ready"": [
      ""语音合成与配音:M02""
     ],
     ""b15_report_conflict"": [
      ""图像生成与视觉设计:M01""
     ],
     ""b15_report_ready"": [
      ""图像生成与视觉设计:M01""
     ],
     ""b15_spec_conflict"": [
      ""图像生成与视觉设计:M02""
     ],
     ""b15_spec_ready"": [
      ""图像生成与视觉设计:M02""
     ],
     ""b16_report_conflict"": [
      ""视频生成与自动剪辑:M01""
     ],
     ""b16_report_ready"": [
      ""视频生成与自动剪辑:M01""
     ],
     ""b16_spec_conflict"": [
      ""视频生成与自动剪辑:M02""
     ],
     ""b16_spec_ready"": [
      ""视频生成与自动剪辑:M02""
     ],
     ""b17_report_conflict"": [
      ""推荐排序与广告:M01""
     ],
     ""b17_report_ready"": [
      ""推荐排序与广告:M01""
     ],
     ""b17_spec_conflict"": [
      ""推荐排序与广告:M02""
     ],
     ""b17_spec_ready"": [
      ""推荐排序与广告:M02""
     ],
     ""b18_report_conflict"": [
      ""预测异常与风险:M01""
     ],
     ""b18_report_ready"": [
      ""预测异常与风险:M01""
     ],
     ""b18_spec_conflict"": [
      ""预测异常与风险:M02""
     ],
     ""b18_spec_ready"": [
      ""预测异常与风险:M02""
     ],
     ""backtest_spec_conflict"": [],
     ""backtest_spec_ready"": [],
     ""beat_tick"": [
      ""M95""
     ],
     ""c01_report_conflict"": [
      ""数据采集与清洗:M01""
     ],
     ""c01_report_ready"": [
      ""数据采集与清洗:M01""
     ],
     ""c01_spec_conflict"": [
      ""数据采集与清洗:M02""
     ],
     ""c01_spec_ready"": [
      ""数据采集与清洗:M02""
     ],
     ""c02_report_conflict"": [
      ""数据标注与标注质量:M01""
     ],
     ""c02_report_ready"": [
      ""数据标注与标注质量:M01""
     ],
     ""c02_spec_conflict"": [
      ""数据标注与标注质量:M02""
     ],
     ""c02_spec_ready"": [
      ""数据标注与标注质量:M02""
     ],
     ""c03_report_conflict"": [
      ""合成数据生成:M01""
     ],
     ""c03_report_ready"": [
      ""合成数据生成:M01""
     ],
     ""c03_spec_conflict"": [
      ""合成数据生成:M02""
     ],
     ""c03_spec_ready"": [
      ""合成数据生成:M02""
     ],
     ""c04_report_conflict"": [
      ""预训练与继续预训练:M01""
     ],
     ""c04_report_ready"": [
      ""预训练与继续预训练:M01""
     ],
     ""c04_spec_conflict"": [
      ""预训练与继续预训练:M02""
     ],
     ""c04_spec_ready"": [
      ""预训练与继续预训练:M02""
     ],
     ""c05_report_conflict"": [
      ""监督微调:M01""
     ],
     ""c05_report_ready"": [
      ""监督微调:M01""
     ],
     ""c05_spec_conflict"": [
      ""监督微调:M02""
     ],
     ""c05_spec_ready"": [
      ""监督微调:M02""
     ],
     ""c06_report_conflict"": [
      ""参数高效微调:M01""
     ],
     ""c06_report_ready"": [
      ""参数高效微调:M01""
     ],
     ""c06_spec_conflict"": [
      ""参数高效微调:M02""
     ],
     ""c06_spec_ready"": [
      ""参数高效微调:M02""
     ],
     ""c07_report_conflict"": [
      ""对齐与偏好优化:M01""
     ],
     ""c07_report_ready"": [
      ""对齐与偏好优化:M01""
     ],
     ""c07_spec_conflict"": [
      ""对齐与偏好优化:M02""
     ],
     ""c07_spec_ready"": [
      ""对齐与偏好优化:M02""
     ],
     ""c08_report_conflict"": [
      ""评测基准与排行榜:M01""
     ],
     ""c08_report_ready"": [
      ""评测基准与排行榜:M01""
     ],
     ""c08_spec_conflict"": [
      ""评测基准与排行榜:M02""
     ],
     ""c08_spec_ready"": [
      ""评测基准与排行榜:M02""
     ],
     ""c09_report_conflict"": [";
}
