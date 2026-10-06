# Phase 1 — Valuation contract v1

## VERIFIED FACT — 实现合同

`apps/api/services/valuation.py` 是只读合同，不改 schema、不改 Asset UUID 或外键、不重写原币账本、Policy、Journal 与历史快照。

输入：household base_currency、一次 UTC as_of、独立 position rows、独立 cash rows、截至 as_of 的直接/反向 FX。输出：version、base_currency、as_of、quality status/reasons、recommendation_ready、Decimal 聚合、positions-only weight scope、逐项 amount currency / native amount / base value / quantity / quote currency / source / observation / price unit multiplier / FX rate/source/time/direction。

计算：reported `market_value` 必须带 `market_value_currency`；不从 `Asset.currency`、账户币种或报价币种猜测金额币种。未报告 market_value 时用 quantity × market_price，币种为 market_price_currency。`GBp` 区分大小写，倍率 0.01 后归一为 GBP，再做 FX；reported amount 自己的币种与 quote currency 独立，amount 和 price unit multiplier 分开记录。cash 使用自身 currency。原始数量与金额不变。

只有相同规范币种允许 identity 1。异币种必须有效正数 finite FX，或对应反向倒数。无 triangulation、无 future fill、无 stale carry-forward、无汇率 1 fallback。完整聚合用 Decimal，显示才舍入 0.01；不能从各显示项舍入后重算总额。

数据质量：24h freshness 是本阶段保守估值 readiness 合同，不修改 Owner 已发布的 Guardian staleness_days / concentration / allocation thresholds。价格/余额观察或 FX 缺失、未来、超过 24h，金额币种缺失、非 finite 数值、无价格且无 reported value、derived quote 非正数 → INCOMPLETE；total、现金/持仓 subtotal 为 null，不返回看似完整的 partial total，不把漏掉资产的权重称作有效。精确 24h 边界有效。

manual Position 的 market_price/market_value 是人工成本估值，标 COST_ESTIMATE，允许展示明确标注的成本总额；recommendation_ready=false。CSV 等带来源与 observation 的 reported value/price 是报告估值，并不宣称来自实时 feed。

## 使用者与权重

- Portfolio wealth_summary：共用 converted entries；position/cash 分开查询后累计，彻底消除两位置 × 两现金 JOIN 放大。资本 bucket summary 是财富金额（含现金）。
- Dashboard：同一 valuation snapshot 的净值、分配、合规、风险和现金卡片；实际 base currency 替换 `$`。未知质量阻止可信显示与审批入口。JSON 保留原币分组和 quality reasons，完整合同附在 DashboardSnapshot.valuation。
- Allocation / bucket drift / 单仓/行业/探索资本规则：继续使用 **positions_only** denominator，现金单独列入财富；这是保留既有规则，不能以“统一估值”为理由把现金混入风险分母。所有位置权重共用相同 converted values 和 position subtotal；财富金额 conservation 包含现金，但不冒充位置权重。
- Guardian monetary intelligence：使用同一 converted entries / as_of；未知质量返回明确 UNAVAILABLE evaluation，不能当 passed。主入口有当前账本时返回 current_ledger 的 transient analysis_findings；没有当前账本的旧 plan/snapshot evaluation 继续历史合同。
- Research 的三个 evidence collectors 共用合同；两个研究 pipeline 在不可推荐质量下停止分析/生成 memo。research_run_id 标记的草稿在 confirm_draft 再验证质量，409 阻止批准；通用人工 Journal 确认保留原 lifecycle。拒绝、历史纠正、历史读取不被拦截。
- 没有 FX 上下文的旧纯 PortfolioIntelligenceService 对多币种输入明确拒绝，不再直接相加。生产新证据源使用共同合同；未建设新的优化器。

## 兼容影响与 OPEN QUESTION

NetWorth.total_value 从 string 扩展为 nullable string；Dashboard/summary 增加质量和来源字段。未知旧记录保留但显示 INCOMPLETE，需要新的可核对报告估值；不会自动补历史币种。人工成本录入不再产生可批准的研究建议。旧 allocation deploy/sell 响应增加 unavailable/approval_eligible=false 且列表为空。

当前账本 Guardian 不创建引用无关旧快照的事件，因此 API 返回 persisted=false，evaluation_run.id=null，analysis_findings 和 events 分开；Next UI 已处理该分支，历史 API/历史事件保持。没有引入伪造 event UUID。持续历史追踪需 Owner 审查新估值快照 schema：建议新增 append-only valuation_snapshots(id, household_id, base_currency, as_of, quality_status, inputs_json, totals_json, input_hash, contract_version)，再为 guardian_events 增 nullable valuation_snapshot_id，放宽旧 portfolio_snapshot_id 非空约束并加“恰好一种快照引用”的 CHECK；分别设计两个 partial unique 索引。历史行保持原引用，禁止回填重算历史结果。**此方案未实施、未运行 migration，必须单独审查**。

市场开闭市 calendar、供应商 source timestamp vs importer observation、FX 多来源优先级/冲突、税费与 restricted accounts、跨账户交易能力、负债/short 权重以及空账本可推荐范围仍待设计。24h default 对周末/休市保守阻断；不能偷偷放宽。
