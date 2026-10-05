日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证/需Owner决定。

# 限制与未验证项

真正发布阻碍：无DeepSeek credential导致真实Committee未验；Yahoo公共数据使用/永久证据留存权限未确认，生产默认disabled，可换授权adapter。

其它非阻碍限制：
- 24h freshness周末/假期保守阻断，不擅自放宽；现金需要近期Owner确认，refresh不能假装确认余额。
- public provider可能timeout/rate limit/metadata错；明确fail closed，精确ticker相似产品绕过已修。
- targets为versioned household配置引用published Policy；旧prose不自动重写。未知custom/max_drawdown等enabled规则阻断，Owner明确规则后再评估。
- ETF杠杆/equity look-through是Owner attestation；金额plan没有fees/spread/tax/股数lot。
- Guardian positions-only、wealth drift含cash；金额同源，比例分母不同，历史规则保持。
- ledger/config/Policy/quote/FX改变或candidate过期须重新生成与Committee，不批准另一份未审金额。
- dev5high/ESLint9 EOL；生产无dev工具，不宣称做过OS漏洞/生产渗透/AI外发验证。
- backtest只有typed boundary/EVIDENCE_ONLY/DEFERRED，旧analytics实验，不输出新虚构metrics；MC/optimizer未实现。
- deployed SHA UNKNOWN；现场schema/data/域名/backup未接触，只能以隔离schema测试推断兼容。

RECOMMENDATION：Owner只处理凭据/数据许可和真实smoke，再决定release；完成此次Sprint即停止，不自动扩大scope。
