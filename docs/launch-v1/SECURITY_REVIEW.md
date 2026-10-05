日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证/需Owner决定。

# 依赖、安全与许可证

VERIFIED FACT：frontend生产图0漏洞；全图5high来自同一braces advisory传播：eslint-config-next→@next/eslint-plugin-next→fast-glob→micromatch→braces。braces3.0.3此advisory没有安全可用patch；npm建议降Next配置至14.2.35，与Next16不匹配，未force修复。生产Docker在builder之后prune --omit=dev，最终镜像实际检查见TEST_REPORT。

ESLint9.39.5按[官方支持表](https://eslint.org/version-support/)已EOL，当前React插件peer尚不兼容10。RECOMMENDATION：维护peer兼容升级，受控源码中运行lint，不接收不可信巨型模式。INFERENCE：主要开发/CI可用性风险，未发现生产引入链，不是全依赖零风险承诺。

扩展Python审计发现此前prod0只是npm，不能代表Python：multipart0.0.20、Starlette0.38.6和pytest8.3.4有公告。升级FastAPI0.142.2/Starlette1.7.0/multipart0.0.32/pytest9.0.3覆盖已公告patch范围，完整回归；requirements.lock固定prod/transitive，requirements-dev分离pytest/Ruff。prod及dev pip-audit均0已知漏洞。

主要公告：[Starlette high](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq)、[multipart high](https://github.com/Kludex/python-multipart/security/advisories/GHSA-pp6c-gr5w-3c5g)、[multipart其他边界](https://github.com/Kludex/python-multipart/security/advisories/GHSA-5rvq-cxj2-64vf)、[非默认upload配置](https://github.com/Kludex/python-multipart/security/advisories/GHSA-wp53-j4wj-2cfg)、[FastAPI notes](https://fastapi.tiangolo.com/release-notes/)。主要条件为HTTP表单/复杂multipart，非默认file配置分别披露；旧生产是否可利用UNKNOWN，没有把本地升级称生产修复。

新网络仅固定Yahoo symbol/FX查询，DeepSeek只有Owner确认preview后发送结构化家庭证据。不新增broker/analytics/遥测，Next build/runtime关闭默认匿名telemetry。timeout/no redirect/URL encoding，symbol不能指定任意host。已有SDK可能行为不等于已实测，无key时未做真实AI外发验证。

没有secret写入代码、测试、报告、memory或PR。Owner key仅bootstrap，browser不持久存key；cookie+Origin+hash/key revoke。生产缺SHA/time mutation gate拒绝；Yahoo缺已确认访问授权拒绝，开关不是法律许可。Linux DeepSeek用安全平台注入环境、既有explicit opt-in，不把secret写到.env示例/命令行/日志。

Folio audit SHA a8fb452b2955e7173ccad3bda637d26aeda75db2，MIT ©2026 Matthias Isler。本Sprint no direct code reuse，无server.ts/SPA/metrics/test源码复制；algorithm-concept reuse为provider/contribution-first，interface-design reuse为drift/provenance。没有新增必须的Folio代码MIT notices；未来复制实质代码需保留MIT，market data rights独立确认。

OPEN QUESTION：pip/npm audit不覆盖OS镜像、生产网络/HTTPS/渗透测试；没有完整OS扫描承诺。原其它项目容器未修改。
