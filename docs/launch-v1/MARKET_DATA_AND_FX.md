日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证或需Owner决定。

# 行情、FX 与共同估值

VERIFIED FACT：独立InstrumentProvider.search/identify、MarketDataProvider.price、FXProvider.fx。当前YahooPublicProvider：固定HTTPS host、编码identifier、12s timeout、不follow redirect、不请求news、不回退模拟值。业务通过配置factory registry核对来源，不硬编码vendor。

价格含UUID/provider_id、positive price、currency、as_of、provider、OBSERVED/DELAYED；market_observations append-only。FX含base/quote、positive rate、time/source/quality，使用既有FX记录，candidate固化实际rate/source/time/direction。GBp→GBP倍率0.01；逆向FX直接除原rate，不先舍入倒数。

valuation-v1：base/as_of、nullable total、status、ready/reasons；每项native amount/currency、price source/time/quality/unit、FX原rate/source/time/inverse。Dashboard、资本桶、Guardian、contribution同converted values。风险concentration保持positions_only分母；wealth/战略drift使用total_wealth_including_cash，scope明确，不偷偷改变20%规则。

缺失/未来/超过24h/非有限/非法币种/负金额→INCOMPLETE/null aggregate，阻断推荐。只有同币种identity允许1，不同币种不假设1。不报价时人工cost标COST_ESTIMATE，reported import值不替代新流程实价。未持有target也必须price/FX齐全。现金确认同样24h，refresh不改真实余额/数量。

VERIFIED FACT：实测VTI搜索、BRK.B身份/价、CNYUSD=X和语义ETF候选成功；另有timeouts。DELAYED不是realtime；周末价格过期会阻断，等待新价。

OPEN QUESTION：Yahoo公共端点未取得已确认生产使用/长期证据留存许可/SLA；生产默认拒绝。只有已有明确访问许可才设置COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED=1，否则换授权provider。开关不授予许可。[Yahoo服务条款](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)对一般自动收集要求许可；Finance端点适用授权未取得。这是项目风险证据，不是法律结论。没有行情转载权假设，也不向行情provider发送家庭持仓。

RECOMMENDATION：Owner选定有使用/留存权的provider，验证交易时段、FX方向与价质量。费用/spread/实际成交价由人工执行核对。
