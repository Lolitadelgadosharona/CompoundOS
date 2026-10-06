# CompoundOS × Folio Phase 1 — Implementation report

日期：2026-10-04 Pacific。授权来源：本任务 Owner 明确授权隔离工作分支修改代码、测试和文档；超越此前审计只读授权，但仅覆盖基线、安全维护、现有估值正确性与虚构建议隔离。本阶段没有 Folio code integration。

## 10 点 executive summary

1. **VERIFIED FACT**：从最新核验 GitHub main `20ceca579b9678c17a1122e2d9b9873812f7fa55` 创建隔离本地分支；未混入未合并 PR。
2. **VERIFIED FACT**：PR117/118/119 仍为 OPEN/DRAFT，其 CI 失败不是修复分支依赖；原目录未提交文件、九份审计文档均保留。
3. **OPEN QUESTION**：deployed SHA **UNKNOWN**；GitHub deployments 为空只表示没有可取得的元数据。没有部署，不宣称生产问题解决。
4. **VERIFIED FACT**：20% concentration fixture 修正；验证恰好20%不告警、超过20%告警，阈值不变。
5. **VERIFIED FACT**：Next16.3.8、sharp0.35.5、PostCSS8.5.28、Vitest4.1.11 与锁图维护；prod audit 从5降为0，critical消除。
6. **VERIFIED FACT**：仍有5个 dev high（同一未修复 braces advisory 传播）；ESLint9 EOL 与 React plugin v10 peer compatibility 尚未解决。没有 force 自动修复，不宣称全依赖受支持/安全清零。
7. **VERIFIED FACT**：valuation-v1 明确 base/as_of/native currency/quote & FX provenance/unit/quality，用共同 converted values 修复异币种相加和 position/cash JOIN 放大。
8. **VERIFIED FACT**：缺失/未来/过期/币种不明返回 INCOMPLETE/null total；人工成本 COST_ESTIMATE 不伪装行情；research generation 和 research draft approval fail closed。固定 deploy/sell 与 constraints_checked 清空并明确 unavailable。
9. **VERIFIED FACT**：合成和新建隔离 PostgreSQL 测试覆盖 USD/CNY/EUR、正反FX、GBp、时间边界、金额守恒、统一位置权重、审批阻断与 current-ledger Guardian。最终验证结果见下表。
10. **RECOMMENDATION**：Owner 先审查 nullable API/保守 freshness/Guardian transient analysis 兼容影响和 schema 提案，再授权下一阶段 Resolver；本阶段结束即停止，不自动进入回测/月供/优化器。

## 基线与边界

| 项目 | 核验事实 |
|---|---|
| 原 repo root | `/Users/richardwang/Projects/CompoundOS` |
| 原 branch / HEAD | `pe-004c-decision-evidence` / `1e70f0407278f4ee8db868192933f356278e7fc2` |
| remote | `https://github.com/Lolitadelgadosharona/CompoundOS.git` |
| GitHub main / worktree base | `20ceca579b9678c17a1122e2d9b9873812f7fa55` |
| 本地实施分支 | `codex/compoundos-phase1-valuation`；未提交 |
| 实施 worktree | `/Users/richardwang/Documents/Codex/2026-10-04/referenced-chatgpt-conversation-this-is-an/work/compoundos-phase1` |
| PR117 | OPEN/DRAFT `pe-002.2a-cio-query` / `6584d9f2390fe956c0cd0050b076b4b9de2b23f9` |
| PR118 | OPEN/DRAFT `pe-004a-decision-workspace` / `67e4c5d9b2c65c07789e368c3cab762c632458c8` |
| PR119 | OPEN/DRAFT `pe-004c-decision-evidence` / `1e70f0407278f4ee8db868192933f356278e7fc2` |
| GitHub CI | 核验既有 main run32035280858/PR checks；infrastructure success，backend/frontend失败。未运行新的 GitHub CI，不改远程状态 |
| 部署 | deployments API `[]`，deployed SHA UNKNOWN |

原目录 status 起止相同：untracked `docker-compose.local.yml`、`docs/LOCAL_DEVELOPMENT_NOTES.md`、`docs/folio-integration/`、`requirements.local.txt`；tracked diff为空。本地 PR119 的 DecisionWorkspace 改动没有带入新 worktree，也不存在本阶段必须依赖它们的代码。

所有写库测试只连接新建容器 `compoundos-phase1-20261004-pg` 的 `compoundos_phase1_20261004_test`，localhost55464，PostgreSQL16.6；原有 CommerceOS/生产容器未使用。该新 DB 执行仓库既有 migrations head 0034 并由 tests fixture truncate **测试表**；没有新增 migration，没有触碰真实持仓/Policy/生产数据库。没有连接券商、执行交易、运行生产迁移、部署、commit/push/PR/merge。

## 实施与修复依据

- concentration 首次复现：1failed/13passed，JNJ21%、PG24% 却断言0警告。fixture改成6项16.7%分散仓位，新增20%边界验证；20/40/10%的已有常量、已发布Policy未改。
- 其他可明确判定的旧测试修正：revision测试按已有0002的VARCHAR64合同检查，不重命名0032历史revision；committee confidence测试使用真正invalid值，不把已由0032允许的low当违规；无macOS通知adapter测试显式模拟非macOS；heartbeat测试用barrier保证续租先于子进程release，生产worker保持原拒绝已释放租约的行为。三项基线失败在原main临时只读快照复现；heartbeat孤立可过、全图重复失败并从相同0.3秒计时竞争定位，修复测试同步。
- 共同估值、单位、readiness、JSON/UI、evidence及approval路径见 PHASE1_VALUATION_CONTRACT.md；金额按原币与来源计算，舍入仅发生在展示。反向FX直接除以观察rate，避免先四舍五入倒数后乘大金额的微小误差。
- Portfolio/Dashboard/Guardian货币金额使用共同计算。风险分配保持 positions_only，不擅自把cash加进20%规则分母；wealth bucket金额含cash，两个scope明确区分。
- 当前账本Guardian analysis_findings为transient，不写成绑定旧snapshot的历史event；旧历史查询/plan snapshot lifecycle保持。前端明确“未评估”，不会把skipped、INCOMPLETE/COST_ESTIMATE显示为阈值通过。
- 固定 deploy GOOGL/BRK.B/VOO 比例、sell JNJ/PG、虚构现金收益和constraints_checked已从真实接口移除，返回unavailable、approval_eligible=false、空建议/空约束；没有替换成新optimizer。

## 最终验证

| 检查 | 结果 |
|---|---|
| backend full suite，新隔离DB | 1493 passed /136 warnings，179.68s；最终冻结代码版本全通过 |
| 合成估值+concentration focused | 41 passed（26估值 +15concentration/portfolio） |
| backend Ruff | All checks passed |
| frontend full suite | 253 passed /14 files |
| frontend type-check / lint / production build | 全通过，Next16.3.8 |
| npm ci | 项目npm10.9.8通过，ignore-scripts |
| prod npm audit | 0 / exit0 |
| 全图 npm audit | 5high / exit1，剩余已详述 |
| git diff --check / Python compile | 通过 |
| GitHub CI / production deployed behavior | NOT VERIFIED；无push/deploy |

完整suite覆盖现有Policy、Journal、Guardian、CSV导入、权限/API及前端回归。新增合成测试明确使用两持仓和同账户USD+CNY两现金，财富330USD、位置300USD，bucket不放大，Dashboard与Guardian读数一致；人工成本和坏数据分别阻止memo批准且不创建confirmed snapshot。未连接真实行情或FX；不把测试数据100k/月供当真实配置。

## 文件清单、兼容与回滚

完整文件清单与git status/diff-stat随 outputs 提供；tracked diff-stat不含untracked新增文件，补充清单包含 valuation.py、test_valuation_contract.py 和本阶段4份文档。仓库MASTER_PLAN只追加本阶段授权/本地review说明，不更改历史Sprint结论。

兼容变化：NetWorth.total_value 可为null；DashboardSnapshot增加valuation/cash_position；allocation增加quality/scope；summary增加quality/reasons；research来源的approval在数据不可信时409；旧pure多币种helper拒绝无估值输入；deploy/sell无真实建议；Guardian current-ledger evaluation_run.id为null、persisted=false、events=[]，新analysis_findings与历史events分开。ESLint开发支持不足仍是维护风险。

回滚（仅方案，本次未执行）：原目录从未切换/被改动，继续使用它即可；若Owner不接受隔离修改，保留patch与worktree，然后切回原目录。不要运行reset --hard/clean或删除audit目录。本阶段无新schema/真实数据改写，因此无生产数据回滚migration；未来若授权发布，应以本阶段base的已知应用/lock版本整体回滚，不重算历史快照。新建测试容器暂保留用于复核；可先stop，清理前确认仅该container/new DB，未自动删除。后续检验必须继续避免复用真实DB。

## 待审查事项与下一阶段

**OPEN QUESTION**：部署SHA；24h保守freshness的交易日calendar；importer observation和真实provider quote timestamp差异；provider权利/FX来源冲突；旧无金额币种资料的可核对新估值；受支持ESLint工具链与braces官方修复；发布镜像dev dependencies；Guardian ledger valuation的历史持久化。

**RECOMMENDATION**：审查 PHASE1_VALUATION_CONTRACT.md 中的append-only valuation_snapshots及guardian_events双来源FK方案；需要migration时另行授权，没有在本阶段实施。Resolver具体API、候选/歧义、Asset UUID/provider mapping、GBp/source metadata与验收案例详见 PHASE1_RESOLVER_NEXT_DESIGN.md，只作设计。

已更新CompoundOS Latest，记忆明确记录本地授权范围和未部署状态，后续开发统一Codex。停止等待Owner review；没有自动进入Resolver/回测/月供/优化器。
