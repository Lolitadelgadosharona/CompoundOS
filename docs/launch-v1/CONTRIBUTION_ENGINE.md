日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证或需Owner决定。

# Contribution-first-v1

VERIFIED FACT：Decimal确定性算法，无SELL/交易/账本写入。100000USD/10000CNY是用户用例/UI初值，不是全局配置；API按家庭保存base、initial cash预算、monthly金额/币种、UUID正权重合计100。

算法：共同current value→FX换算计划贡献→post-total→正缺口=max(0,target×post-total-current)→受现金floor/预算限制按缺口比例分配→金额向下到分→最大余数/UUID稳定tie-break→余数保留cash。缺口为零的overweight不买；新钱扩大分母后旧overweight可能成为underweight，因此不承诺旧overweight永远不买。

monthly为计划资金，不是到账记录：post-total=实际财富+计划贡献。initial使用RECORDED_CASH：post-total不变、预算不得超过实际现金，不把100k重复增加财富。买入是base币金额计划，Owner自行换汇下单。

守恒：BUY总和+retained_cash=原FX换算贡献；sub-cent尾差保留并显示rounding_remainder，不静默丢失。非target已有资产仍纳入wealth分母。输出target/current/post weights、signed absolute_drift百分点差、relative=差/target、under/over、buy_amount/reason/funding/MANUAL；absolute_drift是兼容字段名，数值有正负。

候选不等于可信建议。price/FX缺失直接unavailable；BLOCKED规则候选可展示但不能Committee/approve。现金floor无法满足时按既有warning/critical语义旗标或阻断。ETF杠杆/look-through由Owner核实，标OWNER_ATTESTATION，不凭ticker推断。

RECOMMENDATION：费用、税、整数股/最小lot、换汇spread人工确认。月供calendar与advanced optimization不是此次发布门槛。
