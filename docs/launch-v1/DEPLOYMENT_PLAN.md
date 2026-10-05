日期：2026-10-05。VERIFIED FACT=源码/测试/探针证据；INFERENCE=推断；RECOMMENDATION=建议；OPEN QUESTION=未验证/需Owner决定。

# Owner-controlled Production Deployment

方案，未执行生产迁移/部署/merge。deployed SHA UNKNOWN不猜测。local镜像不是production release；不要同时误启compose.yaml与docker-compose.yml。

1. Owner review PR，确认DeepSeek与市场数据使用/留存许可。Yahoo开关不授予许可；否则提供授权adapter。
2. staging脱敏授权数据验证；生产backup带校验并证明restore，不把production DB URL用于tests。
3. Owner决定merge并记录最终40hex release SHA，从clean checkout build，两image同SHA/实际UTC BUILD_TIMESTAMP/APP_VERSION0.2.0/API_INTERNAL_URL=http://api:8000，复跑CI/security。
4. 安全平台注入ENVIRONMENT=production、DB_PASSWORD、COMPOUNDOS_PUBLIC_ORIGIN=https://实际域名、CADDY_DOMAIN和凭据。Linux DeepSeek用COMPOUNDOS_DEEPSEEK_API_KEY及COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1。不要secret写Git/命令行/报告；Owner key用原bootstrap安全创建。
5. 推荐docker-compose.yml，沿用既有db/pgdata，新增web与Caddy同Origin。config命令可能展示env，不公开输出。compose.yaml是本地/CI另一套volume，不当旧生产数据库迁移路径。
6. Owner明确执行一次：docker compose -f docker-compose.yml run --rm --no-deps --entrypoint alembic api upgrade head (DB/Redis已ready、新release image)。确认0035_launch_foundation。正常startup默认COMPOUNDOS_RUN_MIGRATIONS=0，不在restart隐式迁移。
7. Owner启动api/web/caddy，/health schema及/api/version SHA/time/version/TRACEABLE与image labels匹配；HTTPS Secure cookie/Origin实际域名一致。API仅loopback，不外露DB/Redis。
8. 真实smoke search VTI/QQQ/VXUS/SGOV/BRK.B/semantic候选，明确exchange；录实际account/quantity/cost/cash；fresh price/FX，核对USD/单位/方向/provenance。配置自己的targets、CNY月供与initial cash。bad/stale/ambiguous/Policy不确定必须阻断。
9. Owner审阅preview再Ask Committee；核对hash、evidence references/数字来源、Policy/Guardian。Approve/Reject仅Journal/Audit/manual plan，实仓quantity/cash不变，测试logout/key revoke。
10. 记录release SHA/digest/deploy时间/DBrevision/smoke后Owner决定开放，监控provider failures/error，fail closed，无broker订单外发。

回滚：暂停新写，选择提前准备的向前schema-compatible rollback image或roll-forward补丁，保留0035表/证据。旧0034镜像可能mutation gate拒绝0035，不能保证可直接恢复写入；不得自动downgrade删历史。有research关系回填也视为非空，downgrade会拒绝。只有V1七表全空且backup已验证才允许空staging迁移回退。不得删Journal/Policy/Asset真实历史。

OPEN QUESTION：既有host/volume/domain/restore和真实credentials未验证，Owner准备生产时确认。本机其它项目3000/8000不是CompoundOS。
