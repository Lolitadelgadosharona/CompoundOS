日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证或需Owner决定。

# Phase 1 独立复核

VERIFIED FACT：原GitHub main/base为20ceca579b9678c17a1122e2d9b9873812f7fa55，Phase1基线commit为7a645a497f00329fbfb4220dea25c7dc7382f390。审查清单39/39文件SHA256相符；独立重跑1493 backend/253 frontend均通过，类型/构建通过，并非照抄旧报告。

原repo /Users/richardwang/Projects/CompoundOS 保留在pe-004c-decision-evidence /1e70f0407278f4ee8db868192933f356278e7fc2，tracked diff为空、4项untracked目录/文件保留。PR117/118/119仍OPEN/DRAFT、infra通过、backend/frontend失败；未带入其未合并代码，新分支不依赖这些PR。deployed SHA UNKNOWN；GitHub deployments为空不证明没有部署。

|复核项|结论及本Sprint补强|
|---|---|
|共同估值|KEEP valuation.py：positions/cash独立聚合、同base/direct/inverseFX/GBp|
|坏数据|KEEP INCOMPLETE/null；不按1/零/剔除；reported值不能掩盖无效价格，负金额不静默纳入|
|成本|KEEP COST_ESTIMATE；新流程每项持仓/目标要求实价|
|重复累计|两positions×两cash回归，独立SQL不会笛卡尔放大|
|规则|默认20/40/10不变，warning/critical区别保留；同UUID跨账户合并concentration|
|历史/IDs|原币quantity/cost/cash、AssetUUID、publishedPolicy、confirmed snapshot不重写|
|审批绕过|共享Journal确认钩子重新验证，改草稿不能移除immutable来源关系|
|虚构建议|固定deploy/sell unavailable，bond/benchmark DEMO、旧metrics EXPERIMENTAL|
|迁移|0035新增表/触发器/来源关系回填，只在新_test DB验证|
|兼容|nullable/freshness沿用，same-origin前端；新流程写入需0035|

OPEN QUESTION：没有生产数据/host/deployedSHA，不称生产问题已解决。此前Phase1无commit/push授权仅是当时范围；此次明确授权逻辑commit、条件安全push/PR，merge/deploy仍未授权。所有审计原文保留。
