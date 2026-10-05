日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证/需Owner决定。

# 复用决策流程与防绕过

VERIFIED FACT：candidate→published Policy→existing Guardian→existing CommitteeSession/Evidence/Report→existing Decision Draft→Owner confirm/reject→confirmed snapshot+Audit+Learning reviews→MANUAL plan。没有新Committee/Journal/交易生命周期。

配置、候选、observations、candidate↔decision↔Committee和research来源是新增append-only evidence，canonical JSON SHA256。既有OwnerDecisionService确认保留30/90/365 reviews。拒绝Audit保留关系；既有人写draft discard语义不改。

|关口|实际验证|
|---|---|
|Preview|fresh账本/Policy/数据/Guardian；显示将发送的证据/hash，不调用LLM|
|Ask Committee|Owner明确同意preview/hash，调用既有DeepSeek；通用Committee route也必须contribution-v1协议|
|Report|既有schema/roles/direction；叙述标INFERENCE/RECOMMENDATION、数字FACT仅来自证据；contribution-v1文字含数字拒绝|
|Approval|重新算exact plan/fingerprint、版本/quote/FX/freshness/critical Guardian；必须completed/aligned_with_policy/contribution-v1/真实DeepSeek report，rationale须匹配plan|
|Journal|shared confirm钩子，通用approve不能绕过；既有snapshot/Policy锁/FK保留|
|Manual|仅BUY UUID/symbol/base金额计划；无broker/executor调用，不改quantity/cash|

Policy原版本/20%浓度/40%sector/10%探索不改写，warning不会伪装critical。custom仅支持显式contribution-v1/max_equity_pct；未知enabled规则、禁止资产/杠杆文字无法确定则阻断，不让LLM将其猜成PASS。liquidity/diversification/decision process原文发送Committee，未认可不能批准。ETF产品杠杆/look-through为Owner attestation，未知阻断。

Guardian同时检查current/projected converted positions、confirmed drift/category/staleness与未ack critical事件。旧event不重写；transient findings标persisted=false。household事务锁协调录入/导入/候选/批准；instrument身份锁避免重复UUID。

Owner auth沿用API key一次bootstrap，随机opaque token服务端只存hash、8h HttpOnly/Secure(生产)/SameSiteStrict cookie。无localStorage权威状态；cookie写请求需精确Origin，key revoke使session失效。旧header auth保留，前端同Origin，不把key嵌入静态JS。

Legacy research确认为UNVERIFIED_AI_ANALYSIS_REVIEW/execution NONE，不产生可执行plan；移除草稿research_run_id不能删除immutable FK或绕过freshness。所有真实可批准金额计划必须走governed candidate。

OPEN QUESTION：本机无DeepSeek credential，真实Committee未验。合成provider仅_test，不得授权生产。Owner配置凭据后先审阅preview，才可实际AI smoke。
