# Next-phase Instrument Resolver — design only

**RECOMMENDATION；未实现、未自动授权 G2。** CompoundOS 保持 system of record，Folio 本阶段 no direct code reuse。需要复用时先做 source/license/provider-data-rights 审查。

## 接口与处理顺序

`resolve(query, household_id, market_hint?, exchange_hint?, currency_hint?) -> ResolutionPreview`。
Preview：原始输入、kind(UUID/ISIN/symbol/name)、候选 Asset UUID、ISIN、MIC/exchange、canonical symbol、provider-specific symbol、instrument type、settlement currency、quote currency、quote unit multiplier、provider、capability、as_of、confidence/reasons。
状态：RESOLVED / AMBIGUOUS / NOT_FOUND / UNSUPPORTED / DATA_UNAVAILABLE；provider timeout 与“无此金融工具”分开。

1. UUID：只在 Owner household 的已有账本上下文内选取关联资产；不让自由 UUID 绕过权限。
2. ISIN/MIC-qualified symbol：先查已有 Asset identity，再查 provider search；不截断点号或 exchange suffix。
3. bare symbol/name：查询 provider search 并保留全部候选，多个交易所/不同币种不能自动选第一个或按硬编码 ticker allowlist放行。
4. Owner 选择候选后 preview-only 匹配已有 Asset，差异明确列示；不自动修改 Asset currency/UUID，不合并历史证券、不重写外键。新 identity 的持久化和 provider mapping schema 是单独 Owner review。
5. Quote adapter 返回 price、quote currency、unit multiplier、source timestamp、retrieved timestamp、provider/source、quality、instrument reference；FX adapter 返回 from/to、rate、source/time、quality。进入 valuation-v1，不能用价格成功掩盖 FX 缺失。

## 合同与迁移建议

分离 Domain InstrumentIdentity（Asset UUID + ISIN/MIC/type）与 ProviderInstrumentMapping（provider、symbol、exchange/MIC、quote currency/unit、有效期/capability）。symbol 不作为全球唯一主键；市场数据支持与“资产允许录入”是不同问题。资产原币交易/成本/现金信息不随 provider quote currency 变更。

建议数据库新增 provider mapping 表和可审计 resolution choices；唯一性围绕 provider + instrument identity + mapping validity，保留原 Asset 和全部历史引用。不要在设计阶段直接改现有资产 rows、Policy allocations 或 decision snapshots。映射 schema、历史 backfill/纠错计划、provider contract/data rights 需 Owner 单独批准。

## 具体验收

SPY/VOO/NVDA、BRK.B、0700.HK、SAP.DE、不同交易所同名 ticker、ISIN、已存在 UUID、非法输入、无结果、超时、多候选、供应商 unsupported instrument、GBp 与 GBP、行情币种和现金币种不同、缺失/过期 FX/price。例子仅作合成验收，不成为新的 allowlist 或真实交易配置。

端到端追踪：User Input → frontend exact value → API structured schema → identity resolution → provider capabilities → quote/FX provenance → valuation quality → research readiness → human approval。任何阶段 AMBIGUOUS/DATA_UNAVAILABLE 时都不得生成可批准方案。

USD100k + CNY10k/month 只可作为下一阶段 synthetic case，不能写进真实配置：先换算月供可用资金，优先 contribution-first 补足 policy underweights，再处理 drift/concentration/risk；FX费用、税、交易权限和最小单位缺失时输出模拟/未可用。20%/40%/10% default 以及 Owner 已发布规则均不可静默修改。Resolver、回测、月供、optimizer、Monte Carlo、broker/自动执行本阶段全部未实施。
