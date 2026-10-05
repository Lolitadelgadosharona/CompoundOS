日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证或需Owner决定。

# Canonical Instrument Resolver

VERIFIED FACT：instrument_resolver.py统一词法、动态搜索和canonical Asset身份，launch_providers.py实现InstrumentProvider。没有支持股票/ETF白名单；正则只是语法检查，不证明代码存在。

User Query → provider.search → 候选 → 显式选择provider_id → provider.identify → AssetUUID/provider mapping → market/FX → portfolio/research/CIO。元数据包括symbol/name/exchange/asset_type/currency/provider/provider_id。CASH:USD仅为明确现金身份，现金不是BUY target。

|路径|共同边界|
|---|---|
|Ask CIO/research/start|query_from_question保留点号，动态provider，多候选409/需选择|
|investment workspace|search列候选、select验证provider_id，不猜相似名字|
|manual position/账本|canonical UUID、Owner账户归属、household锁，需verified mapping|
|CSV/import|ledger_identity/normalize_symbol，离线明确unverified、必须币种；未verified/无实价不能推荐|
|旧portfolio draft|保留Owner名称/类别draft，不伪装成已解析证券或可执行推荐|
|contribution|UUID/mapping/observation，不重新解析ticker|

历史compatible身份优先复用UUID；跨交易所、币种或多匹配要求显式映射，不自动合并。instrument级事务锁避免并发创建重复身份；provider分类用于新read projection，不重写历史Asset分类/外键。

精确大写ticker没有exact候选时，不能自动选择类似产品。Yahoo BRK.B曾返回BRKC；修复后US exchange+display完全匹配才采用provider拼写BRK-B，实测BRK.B/BRK-B/NYQ。该次股价as_of为上周五，超过24h因此不可用于新建议。

测试含任意ETF、BRK.B、相似产品误匹配、歧义、无效/outage、UUID/币种冲突。用户示例全由动态provider查询，不维护许可代码常量；语义查询返回Nasdaq100/短债ETF多交易所候选，Owner必须选。

OPEN QUESTION：生产数据访问授权未确认。未来adapter只需实现3个Protocol及factory registry，不重做领域模型，不允许跨交易所猜测。
