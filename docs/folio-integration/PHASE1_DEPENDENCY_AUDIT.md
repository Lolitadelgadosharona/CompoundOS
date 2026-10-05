# Phase 1 — CompoundOS frontend dependency security audit

日期：2026-10-04（Pacific）；registry 查询与本地审计在 2026-10-05 UTC。只代表这次 lock graph，不能证明任何部署已修复。

## VERIFIED FACT — 结果与升级

| 范围 | 修复前 | 修复后 |
|---|---|---|
| 全依赖图 | 17：critical 1 / high 11 / moderate 5 | 5：high 5 / critical 0 / moderate 0 |
| `npm audit --omit=dev` | 5：critical 1 / high 2 / moderate 2 | 0 |

必要升级：Next 与 eslint-config-next 16.2.12 → 16.3.8；Vitest 4.1.10 → 4.1.11；sharp override 0.35.3 → 0.35.5；PostCSS override 8.5.18 → 8.5.28。保留 React 19.1.0、Node 22 和项目 npm 10 要求。重新解析锁文件获得修复后的 nanoid 3.3.19、undici 7.30.0、brace-expansion 1.1.21 / 5.0.12、js-yaml 4.3.2、browserslist 4.29.3、baseline-browser-mapping 2.11.27。

npm 10.9.8 在新旧锁图解析都出现 Arborist `edgesOut` 异常。仅在临时目录使用 npm 11.11.1 生成锁文件（其运行时 Node 22 受支持，但临时 manifest 发出项目 npm engine 警告）；随后项目声明的 npm 10.9.8 `npm ci --ignore-scripts` 成功。没有升级项目 npm engine、全局安装、`audit fix --force` 或跨大版本降级。依赖安装未执行应用 install scripts；前端测试/构建是已审阅 CompoundOS 应用代码的验证。

## VERIFIED FACT — 逐项来源与引入链

下表来自修改前 npm audit 的机器可读记录和旧 lock graph 最短引入链。传播包不代表独立漏洞；不能把 17 个 affected packages 当作 17 个 exploit。

| Package | Severity | 引入链 | Advisory / affected range | 处理 |
|---|---|---|---|---|
| @next/eslint-plugin-next | high | eslint-config-next@16.2.12 → @next/eslint-plugin-next@16.2.12 | 上游漏洞传播；见引入链 | 仍受影响（开发工具链） |
| @vitest/mocker | moderate | vitest@4.1.10 → @vitest/mocker@4.1.10 | [Vitest: Path Traversal / Arbitrary File Read via @vitest/mocker Redirect Mock](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) (>=2.1.0 <4.1.11) | 当前审计已消除 |
| baseline-browser-mapping | moderate | next@16.2.12 → baseline-browser-mapping@2.10.43 | [baseline-browser-mapping process termination on invalid input causes denial of service](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv) (>=2.0.0 <2.11.0) | 当前审计已消除 |
| brace-expansion | high | eslint-config-next@16.2.12 → typescript-eslint@8.63.0 → @typescript-eslint/typescript-estree@8.63.0 → minimatch@10.2.5 → brace-expansion@5.0.7 | [brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash](https://github.com/advisories/GHSA-mh99-v99m-4gvg) (<1.1.17)<br>[brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash](https://github.com/advisories/GHSA-mh99-v99m-4gvg) (>=4.0.0 <5.0.8)<br>[brace-expansion: DoS via unbounded intermediate arrays, bypassing the CVE-2026-14257 mitigation](https://github.com/advisories/GHSA-rgw5-rvv9-x895) (>=4.0.0 <5.0.9)<br>[brace-expansion: DoS via unbounded intermediate arrays, bypassing the CVE-2026-14257 mitigation](https://github.com/advisories/GHSA-rgw5-rvv9-x895) (<1.1.18)<br>[brace-expansion: Quadratic-time expansion of the `{a},b}` rewrite causes CPU denial of service](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr) (<1.1.21)<br>[brace-expansion: Quadratic-time expansion of the `{a},b}` rewrite causes CPU denial of service](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr) (>=4.0.0 <5.0.12)<br>[brace-expansion: DoS via uncontrolled recursion on nested brace groups causing stack exhaustion](https://github.com/advisories/GHSA-qhr7-859c-m2p7) (<1.1.20)<br>[brace-expansion: DoS via uncontrolled recursion on nested brace groups causing stack exhaustion](https://github.com/advisories/GHSA-qhr7-859c-m2p7) (>=4.0.0 <5.0.11)<br>[brace-expansion: DoS via uncontrolled recursion in parseCommaParts causing stack exhaustion](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) (<1.1.19)<br>[brace-expansion: DoS via uncontrolled recursion in parseCommaParts causing stack exhaustion](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p) (>=4.0.0 <5.0.10) | 当前审计已消除 |
| braces | high | eslint-config-next@16.2.12 → @next/eslint-plugin-next@16.2.12 → fast-glob@3.3.1 → micromatch@4.0.8 → braces@3.0.3 | [braces vulnerable to stack-exhaustion denial of service through deeply nested patterns](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) (<=3.0.3) | 仍受影响（开发工具链） |
| browserslist | high | eslint-config-next@16.2.12 → eslint-plugin-react-hooks@7.1.1 → @babel/core@7.29.7 → @babel/helper-compilation-targets@7.29.7 → browserslist@4.28.6 | [Browserslist: Unbounded memory growth (no cache eviction) via distinct query results, leading to eventual OOM](https://github.com/advisories/GHSA-c83g-rgw3-j3cx) (<=4.28.6)<br>[Browserslist: Uncaught crash / prototype write via untrusted browserslist-stats.json custom stats (normalizeStats)](https://github.com/advisories/GHSA-73wf-gq98-2v4g) (<=4.28.6) | 当前审计已消除 |
| eslint-config-next | high | eslint-config-next@16.2.12 | 上游漏洞传播；见引入链 | 仍受影响（开发工具链） |
| fast-glob | high | eslint-config-next@16.2.12 → @next/eslint-plugin-next@16.2.12 → fast-glob@3.3.1 | 上游漏洞传播；见引入链 | 仍受影响（开发工具链） |
| js-yaml | high | eslint@9.39.5 → @eslint/eslintrc@3.3.6 → js-yaml@4.3.0 | [JS-YAML: Quadratic CPU consumption in !!omap resolution (3.x and 4.x) — CVE-2026-59870 fix not backported](https://github.com/advisories/GHSA-5p4m-2wfm-xmqj) (>=4.0.0 <4.3.1)<br>[js-yaml: maxTotalMergeKeys does not limit CPU use for empty merge sources](https://github.com/advisories/GHSA-2883-xcg3-v3hh) (>=4.0.0 <4.3.2) | 当前审计已消除 |
| micromatch | high | eslint-config-next@16.2.12 → @next/eslint-plugin-next@16.2.12 → fast-glob@3.3.1 → micromatch@4.0.8 | 上游漏洞传播；见引入链 | 仍受影响（开发工具链） |
| nanoid | high | next@16.2.12 → postcss@8.5.18 → nanoid@3.3.16 | [nanoid: custom generators can loop indefinitely when size is zero](https://github.com/advisories/GHSA-2v37-7h3g-55p8) (<3.3.18) | 当前审计已消除 |
| next | critical | next@16.2.12 | [Next.js: Unauthenticated Remote Code Execution on windows-hosted servers](https://github.com/advisories/GHSA-p293-qw3h-jr36) (>=16.0.0 <16.3.3)<br>[Next.js: Unauthenticated Remote Code Execution in Image Optimization API when AVIF files are used](https://github.com/advisories/GHSA-2xp9-vwfh-vxw4) (>=16.0.0 <16.3.3)<br>[Next.js: Remote Code Execution in next/og ImageResponse](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j) (>=16.2.0 <16.3.6) | 当前审计已消除 |
| postcss | moderate | next@16.2.12 → postcss@8.5.18 | [PostCSS: incomplete fix of GHSA-6g55-p6wh-862q — attacker-controlled sourceMappingURL reads arbitrary .map files when `from` is unset](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) (<=8.5.22) | 当前审计已消除 |
| sharp | high | node_modules/sharp | [sharp: Vulnerabilities in libheif: GHSA-g89c-p67h-r497 and GHSA-2jg2-4ch7-h545](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c) (<0.35.4) | 当前审计已消除 |
| undici | high | jsdom@29.1.1 → undici@7.28.0 | [undici vulnerable to downstream response desynchronization via retry interceptor](https://github.com/advisories/GHSA-8xcm-r25x-g524) (>=7.0.0 <7.29.0)<br>[undici vulnerable to cross-user information disclosure and parse-time crash via degenerate private cache directives](https://github.com/advisories/GHSA-4cwx-7wf7-3272) (>=7.0.0 <7.29.0)<br>[undici vulnerable to CRLF Injection via blob-like body 'type' property](https://github.com/advisories/GHSA-m8rv-5g2x-5cg5) (>=7.0.0 <7.29.0)<br>[undici vulnerable to cross-user information disclosure via whitespace around equals in Cache-Control directives](https://github.com/advisories/GHSA-jr45-8vmc-qm54) (>=7.0.0 <7.29.0)<br>[undici vulnerable to cookie attribute injection via unsanitized domain and unparsed setCookie fields](https://github.com/advisories/GHSA-v3r7-h72x-cjcm) (>=7.0.0 <7.29.0)<br>[undici vulnerable to Denial of Service via unhandled error in WebSocket permessage-deflate decompression](https://github.com/advisories/GHSA-3wwx-pv8p-q78v) (>=7.28.0 <7.29.1)<br>[undici vulnerable to Denial of Service via orphaned RetryHandler response body](https://github.com/advisories/GHSA-pmjh-fq2x-6v4x) (>=7.11.0 <7.29.1)<br>[undici vulnerable to downstream response splitting via retry interceptor](https://github.com/advisories/GHSA-r53p-7pc4-xj5r) (>=7.0.0 <7.29.1)<br>[undici vulnerable to Denial of Service via unrequested WebSocket subprotocol](https://github.com/advisories/GHSA-rfgv-xxqx-mfg5) (>=7.0.0 <7.29.1)<br>[undici vulnerable to Denial of Service via unbounded decompression of compressed responses](https://github.com/advisories/GHSA-3xpg-4rpp-hhhm) (>=7.15.0 <7.29.1)<br>[undici vulnerable to cross-user cookie disclosure via Set-Cookie caching in shared caches](https://github.com/advisories/GHSA-2jfj-6hjv-fm6j) (>=7.0.0 <7.29.1)<br>[undici vulnerable to response truncation via oversized chunked responses in the dump interceptor](https://github.com/advisories/GHSA-2gqq-gqf2-x968) (>=7.1.0 <7.29.1)<br>[undici vulnerable to TLS certificate validation bypass via dropped connect options in BalancedPool](https://github.com/advisories/GHSA-w293-vg96-wgc3) (>=7.24.1 <7.29.1)<br>[undici vulnerable to caching and replay of unsafe HTTP method responses](https://github.com/advisories/GHSA-8436-99hf-9mmv) (>=7.0.0 <7.29.1)<br>[undici vulnerable to Denial of Service via WebSocketStream unclean close](https://github.com/advisories/GHSA-rx4f-c7p8-82vq) (>=7.0.0 <7.29.1) | 当前审计已消除 |
| vite | moderate | vitest@4.1.10 → vite@8.1.4 | 上游漏洞传播；见引入链 | 当前审计已消除 |
| vitest | moderate | vitest@4.1.10 | [Vitest: Path Traversal / Arbitrary File Read via @vitest/mocker Redirect Mock](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) (>=2.1.0 <4.1.11) | 当前审计已消除 |

## 运行条件与可利用性边界

- Next RCE family：Windows-specific RCE 需要 Windows 环境；AVIF RCE 需要受影响 image optimization 处理攻击者输入；next/og RCE 需要受影响 ImageResponse/OG 流程。相关范围由 Next 16.3.8 覆盖。本项目配置只有 reactStrictMode，app/lib 中未发现 next/image 或 next/og/ImageResponse 调用；不是生产不可利用的证明。Next 框架路由与默认功能仍需按实际运行部署核对。
- sharp/libheif 风险需要处理相应恶意图片；它是 Next 运行依赖，故直接升级而非按“没有应用调用”忽略。
- PostCSS/nanoid 风险涉及解析攻击者控制 CSS/相关输入与碰撞等 advisory 指定条件，Next 构建/工具链引入；当前锁图已覆盖相关审计范围。
- jsdom → undici 是测试依赖链；需要攻击者控制的网络响应/输入进入受影响 HTTP 功能。浏览器目标、YAML、brace-expansion 风险主要在构建/lint 配置或文本/模式处理中。应用接口未找到向这些工具传递用户模式的路径；不代表任意 CI/构建输入安全。
- 剩余 braces 是 `eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces@3.0.3`，一个深层 brace-pattern DoS advisory 传播成 5 个 high。Next 插件 `dist/utils/get-root-dirs.js` 读取 ESLint 的 rootDir glob；本项目 eslint config 使用默认 Next 配置，未开放用户输入 glob。受信任配置中的恶意深层模式或不可信仓库构建仍可触发。
- [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) 明确写明 patched versions: None。没有可信可用修复版本，未强制替换 braces API 或按 audit 建议降级 eslint-config-next 到 14。此问题保留为 **UNRESOLVED HIGH（dev graph）**，不能宣称全图安全清零。
- `frontend/Dockerfile` runner 目前复制 builder 全量 node_modules，因此 dev package 可能物理进入镜像。omit=dev 0 只是分类后的 audit 结果，不是“镜像没有 dev 包”的证明，也不是生产渗透测试。**RECOMMENDATION**：另行核验/prune 发布镜像中的 dev deps、跟进官方 braces 修复。未在本阶段修改 Docker 发布流程或部署。

## UNRESOLVED — 开发工具版本支持

ESLint 9.39.5 的安装 warning 与[官方版本支持表](https://eslint.org/version-support/)一致：v9 于 2026-08-06 EOL，v10 为当前版本。本次查询 v10 最新 10.12.0；eslint-config-next 16.3.8 自身允许 >=9，typescript-eslint 8.71.0 允许 v10，但最新 eslint-plugin-react 的 peer range 仍止于 ^9.7，未声明 v10 支持。因此没有用 force/legacy-peer-deps 强行制造“受支持”的工具链，也没有为了升级撤掉 React lint 规则。**开发工具全面受支持版本要求尚未完全满足**；保留 ESLint 9，记录为 EOL 维护风险。后续需官方插件支持 v10 或单独评审 lint 规则迁移/有维护保障的兼容方案；未购买商业支持。其风险与剩余 braces advisory 分别记录。

## 验证、许可与未验证项

前端 253 tests、tsc、ESLint、Next production build 通过。全图审计 exit 1 是剩余 5 high；prod audit exit 0。CI 原流程只执行 `npm audit --omit=dev`，未来未运行的 GitHub CI 状态不作本地通过声明。

本阶段没有复制/翻译 Folio 源码，没有引入 Folio/Yahoo SDK 或新的市场数据供应商。更新的 lock 包 license metadata 是供应链证据，不是逐文件法律判定；原 Folio license/source audit 仍保留在原工作目录，未覆盖。第三方数据授权、真实部署输入、运行镜像内容、Python 全图最新 advisory 扫描、恶意 payload 复现均 **NOT VERIFIED**，不纳入“已解决”结论。

原始 audit JSON 与依赖树随交付 outputs 提供；advisory 依据 registry 指向的 GitHub 官方记录。不要从用户真实资产或凭证推断攻击面。
