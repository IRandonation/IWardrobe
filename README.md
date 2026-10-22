# IWardrobe

在本机运行的私人衣橱。每个用户独立，电脑和手机尺寸共用一套响应式网页。

当前交付包含 **基础衣橱、BiRefNet Lite 抠图及天气规则穿搭**。已实现真实 PostgreSQL 持久化、登录与会话、私有照片、后台缩略图与 CPU 抠图、衣物编辑、收藏、洗衣/收纳状态、整套推荐及穿着反馈。每个账号独立使用。

## 现在可以做什么

- 独立账号登录、退出；衣物、图片、任务按当前账号隔离。
- 单张或批量上传 JPEG / PNG / WebP；每张最多 20 MB、2000 万像素，每张生成一件衣物。
- 手动建档，编辑类别、颜色、季节、材质、护理和备注。
- 搜索、分类、排序、收藏；记录穿过一次、放入洗衣篮、洗净、收纳和恢复。
- 上传时默认使用 BiRefNet Lite 自动抠图，也可暂不抠图；详情中可手动处理或重新处理。
- 对照原图与最近一次成功的抠图结果，查看耗时、选为展示图或恢复原图。
- 查看后台任务和失败原因，重试失败的缩略图或抠图任务；中断任务可恢复。
- 导入 4 件生成的演示衣物。同一账号重复导入不会产生重复记录。
- 在衣物详情补充厚薄、叠穿层次、袖长/裤裙长、风格、防风和防雨标签；未知信息保留为未知。
- 按城市逐时预报或手动天气，结合出门时段、场合和个人冷热倾向生成最多 3 套有差异的搭配。
- 换一件、记录整套实际穿着、反馈偏冷/合适/偏热及喜欢/不喜欢；下次推荐参考有效反馈。

**尚未实现**：穿着照片中只提取衣服的专用分割、生成式正面重建、HEIC、AI 材质/洗标识别、AI 搭配重排、定时每日推荐、PWA、NAS 部署。现有抠图模型适合单件平铺或悬挂照片，穿着照可能保留人体。演示图片由生图工具生成且已带透明背景；材质与护理字段是人工编写的测试数据。

## 已配置的本机使用方法

在 `D:\Project\IWardrobe` 的 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1 -WslDependencies
```

打开 <http://127.0.0.1:5173>。演示账号保存在 **`.local/demo-accounts.json`**：`demo` 初始有 4 件演示衣物，`demo2` 初始为空。密码随机生成，仅保存在本机被 Git 忽略的文件中，不嵌入前端。可使用自己的 CLI 账号。

停止应用（保留数据和数据库进程）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

需要停止本项目的 WSL 数据库和 Redis 时：

```powershell
wsl -d Ubuntu-22.04 -- bash /mnt/d/Project/IWardrobe/scripts/stop-wsl-deps.sh
```

应用日志在 `.local/logs/`。API 使用 `127.0.0.1:18765`，网页使用 `127.0.0.1:5173`；保留电脑上其他应用的 8000 端口。

## 本机依赖与 WSL 的作用

| 部分 | 本次实际运行位置 |
| --- | --- |
| React / Vite | Windows，Node 24，pnpm 11 |
| FastAPI / arq worker | Windows，项目内 Python 3.12 虚拟环境 |
| PostgreSQL 16 | WSL 内专用用户目录，端口 5433 |
| Redis 6.0.16 | WSL 内专用用户目录，端口 6380，已实测 arq 工作流 |
| 原图 / 缩略图 / 抠图 | 项目 `.local/data/`，只通过鉴权 API 读取 |
| CPU 抠图模型 | Windows worker 子进程；权重缓存 `.local/models/` |

WSL 只用于当前电脑的两个开发依赖。应用使用标准数据库和 Redis 地址，不依赖 WSL API。方案和 Compose 默认 Redis 7；当前 WSL 使用 Ubuntu 提供的 Redis 6.0.16 作本机验证，Redis 7 的 Compose 路径尚未在这台电脑验证。

这台电脑没有 Docker，WSL 现有 ROS 包环境又存在未完成依赖。因此 `setup-wsl-deps.sh` 只验证官方软件源签名、下载并解压包到 `~/.local/share/iwardrobe-runtime`，不执行系统包安装/修复。PostgreSQL 数据也在该专用目录中。脚本面向 Ubuntu 22.04 x86_64，是本机替代方案，不是 NAS 配置。

## 从干净环境安装

需要 Node 22.12+、pnpm、uv，以及可连接的 PostgreSQL 16 / Redis。可复制 `.env.example` 为 `.env` 修改地址。保留 `.env`、`.local/` 和真实照片在版本控制之外。

1. 启动依赖，二选一。

有 Docker 的机器：

```powershell
docker compose -f deploy/compose.dev.yaml up -d
```

本机已存在 Ubuntu 22.04 的 WSL，可使用隔离解压脚本：

```powershell
wsl -d Ubuntu-22.04 -- bash /mnt/d/Project/IWardrobe/scripts/setup-wsl-deps.sh
wsl -d Ubuntu-22.04 -- bash /mnt/d/Project/IWardrobe/scripts/start-wsl-deps.sh
```

2. 安装依赖并迁移数据库。

```powershell
pnpm install --frozen-lockfile
uv sync --project backend --python 3.12 --locked
backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe scripts/bootstrap-demo.py
```

本次 uv 保存在 `.tools/uv/bin/uv.exe`，未改动系统 Python；若没有全局 `uv`，可以用这个路径替代。重跑演示初始化不会重置已有账号密码。

3. 使用启动脚本，或分别运行（Linux/macOS 对应虚拟环境路径为 `.venv/bin/`）：

```powershell
backend/.venv/Scripts/python.exe -m uvicorn iwardrobe.main:app --host 127.0.0.1 --port 18765
backend/.venv/Scripts/python.exe -m iwardrobe.worker
pnpm dev
```

创建自己的账号，密码通过隐藏输入读取：

```powershell
backend/.venv/Scripts/python.exe -m iwardrobe.cli create-user yourname --name "我的衣橱"
```

当前启动配置仅监听本机，开发 HTTP 的 Cookie 未设置 Secure。真实手机拍摄和外部网络访问未验证；需要时再配置受信任 HTTPS、Origin 和 Secure Cookie。数据库演示密码仅适用于这里的回环开发配置。

## BiRefNet Lite 抠图

1. 添加照片时默认勾选“自动抠图”；上传完成后即可浏览，BiRefNet Lite 在后台排队处理，也可取消勾选暂不抠图。
2. 打开单品详情，可点击“后台抠图”或“重新抠图”，失败后可重试。
3. 在“原图 / 抠图结果”之间切换预览；点击“设为展示图”，或回到原图并点击“恢复原图”。选择的是最近成功的结果，之后重新抠图成功会更新其展示图；失败会保留上一次成功结果。

首次使用自动从 rembg 的 GitHub release 下载 BiRefNet Lite 权重，约 224 MB；下载后可离线推理，照片不上传第三方。固定 `rembg[cpu]==2.0.86`，具体依赖见 `backend/uv.lock`。初次下载失败时任务会保留原图并允许重试。升级已有安装需要先执行 `uv sync --project backend --locked` 和 Alembic 迁移，再重启服务。

每次任务启动独立 CPU 子进程，默认两条 ONNX 线程，600 秒内未完成会终止进程。输出为 1024×1024 透明 PNG，进行方向校正、裁边及等比例居中，不补画缺失衣物。界面耗时包含库/模型加载及处理，首次还包含下载；排队时间不计入。

`.env` 可用 `MODEL_CACHE_DIR` 指定缓存目录、`CUTOUT_THREADS` 调整线程数。权重和照片均不提交 Git。界面保留最近一次成功结果，历史成功文件暂不自动清理，以保持已有图片链接有效。之前试用的 U²-Netp 已停用，历史任务和文件仍保留，但不能新建、重试或选为展示图；之前选择的 U²-Netp 展示图回到原图预览。参阅 [抠图实现与验证](docs/validation/cutout-local.md)。

## 天气穿搭试用

1. 在“我的衣橱”导入演示衣物，或录入自己的上装、下装/连衣裙和鞋；在单品详情的“穿搭属性”确认厚薄等属性。旧衣物标签默认未知，系统会提示判断依据不足。
2. 打开“今日穿搭”，搜索并选择城市（中文无结果可尝试英文），设置日期、出门和返回时间、场合、室内/户外及冷热倾向。返回时间早于出门时间表示跨午夜。
3. 点击生成，默认设置按账号保存。也可切换“手动天气”模拟不同条件或离线试用；手动结果始终明确标注，不冒充预报。
4. 对照搭配卡上的真实衣物和理由，点击“换一件”替换同角色单品。没有其他合适衣物会明确说明，衣橱不足三套时只返回实际可用数量；缺鞋等方案显示待补齐。
5. 实际穿着后点击“今天穿这套”，每件衣物计数一次；重复请求不会再次计数。仅允许所选地点当日的完整方案，衣物已修改、待洗或收纳时要求重新生成。
6. 记录冷热和喜好；再次点击可修改或清除。冷热只调整保暖倾向，喜好调整颜色与风格；反馈覆盖保存并重新统计，不因重复提交放大偏好。

天气使用 [Open-Meteo](https://open-meteo.com/) 逐时体感温度、降雨概率、风速，按实际出行时段汇总，支持当天起 7 天的日期。城市搜索和坐标请求使用公开服务，推荐计算与衣物照片留在本机。天气数据按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 署名使用，免费服务适用于符合其条款的非商业用途。

预报缓存 1 小时；刷新失败时仅使用 6 小时内覆盖同一出行时段的缓存，并标明旧预报及获取时间；没有可用缓存时提示切换手动天气。天气结果、衣物属性快照和反馈保存在 Postgres。缓存使用现有 Redis，规则计算无需 GPU 或云端大模型。

推荐是经验规则评分，不是热舒适测量或保暖保证。主要室内活动使用明确提示的常见室温假设；防风、防雨信息未知时不会推断成具备保护能力。可选 LLM 重排与自动识别在后续阶段接入。参阅 [本机推荐验证](docs/validation/weather-outfits-local.md)。

## 项目结构

```text
apps/web/src/
  app/                    会话入口
  pages/                  衣橱页面与筛选
  features/identity/      登录
  features/wardrobe/      单品卡、详情表单、状态操作
  features/capture/       上传与手动建档
  features/jobs/          图片任务与重试
  features/outfits/       今日穿搭、出行设置、整套穿着与反馈
  components/             通用对话框、品牌、错误状态
  lib/                    HTTP 客户端、生成的 OpenAPI 类型
backend/src/iwardrobe/
  main.py                 路由、依赖注入、HTTP 响应
  identity.py             密码、会话、CSRF、Origin、登录限流
  wardrobe.py             建档、更新、穿着、演示导入
  media.py                图片校验、私有存储、缩略图
  image_processing.py     BiRefNet Lite CPU 抠图、透明图、可终止推理子进程
  jobs.py / worker.py      持久任务、派发、租约、重试
  weather*.py             城市搜索、逐时预报、缓存和手动天气
  recommendation*.py      规则组套、偏好、历史快照、穿着与反馈
  models.py / schemas.py   数据库与 API 模型
  cli.py                  创建账号、导入演示数据
backend/migrations/       Alembic 迁移
backend/tests/            PostgreSQL / Redis 集成测试
fixtures/demo/            4 张生成图片、字段、提示词及来源
tests/e2e/                桌面 / 手机视口端到端测试
scripts/                  本机启停、账号初始化、契约生成
deploy/compose.dev.yaml   可选的本机容器依赖
docs/validation/          验收记录
```

数据库中的 `jobs` 是任务状态依据，Redis 只承担派发；worker 每 10 秒补派发排队任务和恢复过期租约。图片任务并发为 1。请求和 worker 都检查归属及账号状态，文件不通过网页静态目录公开。衣物更新携带版本号，旧页面修改返回 409。

## 验证与继续开发

后端测试只操作专用的 `iwardrobe_test` 数据库，并验证名称后才清理测试表。WSL 脚本会创建此库；Compose 用户需自行创建空的同名测试库。

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
pnpm build
pnpm exec playwright install chromium
backend/.venv/Scripts/python.exe scripts/prepare-e2e.py
pnpm test:e2e
```

浏览器测试要求应用和 worker 已启动。准备脚本创建全新的专用测试账号，不修改 `demo` 或真实账号。截图在 `.local/screenshots/`；失败记录在 `test-results/`，均不提交 Git。

API 变更后更新前端契约：

```powershell
backend/.venv/Scripts/python.exe scripts/export-openapi.py
pnpm exec openapi-typescript apps/web/openapi.json -o apps/web/src/lib/generated.ts
```

下一阶段收集真实照片抠图效果和规则穿搭的实际反馈，再按需要接入识别审核与 AI 重排。参阅 [完整技术方案](docs/architecture/technical-design.md) 和 [基础工程验收记录](docs/validation/m0-local.md)。NAS 仍在本机功能闭环后单独实施。
