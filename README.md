# Codex Monitor

在 GitHub Actions 上每小时读取 Tibo（@thsottiaux）的 RSS 动态，用本地关键词规则分析 Codex 额度重置信号，达到 60 分时通过 QQ 邮箱发送提醒。部署完成后，电脑可以关机。

Python 3.10+，仅使用标准库。使用公开 GitHub 仓库和标准 `ubuntu-latest` 托管运行器，可免费运行；无需购买服务器。[GitHub Actions 计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

## 项目文件

```text
codex-monitor/
├── main.py
├── twitter_fetcher.py
├── analyzer.py
├── email_sender.py
├── config.py
├── state_store.py
├── requirements.txt
├── .gitignore
├── .github/workflows/codex_monitor.yml
├── tests/test_monitor.py
└── README.md
```

`state_store.py` 负责在不同 Actions 运行之间保存去重记录。首次正式运行会自动创建仓库文件 `state/processed_tweets.json`，里面只有版本、初始化标记、推文 ID 和处理状态。

## 一、创建免费 GitHub 仓库

1. 登录 [GitHub](https://github.com/)，点击右上角 `+` → `New repository`。
2. 名称填写 `codex-monitor`，选择 **Public（公开）**，勾选添加 README，创建仓库。
3. 解压项目包，在仓库点击 `Add file` → `Upload files`，上传项目文件。**让 main.py 出现在仓库根目录**，不要把外层 `codex-monitor` 文件夹也套进去。上传 `tests` 文件夹时保留目录结构。
4. `.github` 是隐藏目录，拖拽上传时可能漏掉。可以点击 `Add file` → `Create new file`，文件名填写 `.github/workflows/codex_monitor.yml`，将项目中同名文件的完整内容复制进去，再提交。
5. 提交位置选择默认分支，通常是 `main`。最终仓库首页应看到 main.py、config.py、tests，以及 `.github` 文件夹。

使用标准 `ubuntu-latest`，无需设置付费大型运行器。私有仓库消耗账号的免费分钟配额，超额计费规则不同；本教程按公开仓库部署。

## 二、准备 QQ 邮箱授权码

1. 登录 [QQ 邮箱网页版](https://mail.qq.com/)。
2. 打开设置，在账号或账号与安全中找到 POP3/IMAP/SMTP 服务。
3. 开启 POP3/SMTP 或 IMAP/SMTP，按照页面要求验证身份并生成授权码。界面名称可能随版本变化。[授权码操作说明](https://consumer.huawei.com/cn/support/content/zh-cn16108643/)
4. 程序使用授权码登录 SMTP。把授权码保存到下一步的 GitHub Secret 中。

服务器为 `smtp.qq.com`，端口 `465`，使用 SSL 并校验证书。

## 三、在 GitHub 填三个 Secrets

仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，分别创建：

| Name（名称，原样填写） | Secret（值） |
| --- | --- |
| `QQ_EMAIL` | 发件 QQ 邮箱，例如 `123456789@qq.com` |
| `QQ_AUTH_CODE` | 刚生成的 SMTP 授权码 |
| `RECEIVER_EMAIL` | 接收提醒的邮箱，可以是自己的 QQ 邮箱 |

代码中不用填账号或授权码。`GITHUB_TOKEN` 由 GitHub 自动提供，不需要创建，也不需要购买 API Key。

RSS 地址已内置，你可以先不设置它。如以后需要更换，创建可选 Secret `TWITTER_RSS_URLS`，每行填写一个 HTTPS RSS 地址，最多五个；它会替换内置列表。

## 四、允许保存去重记录

仓库 → `Settings` → `Actions` → `General` → `Workflow permissions`，选择 `Read and write permissions` 并保存。工作流自身声明了 `contents: write`，用于保存 `state/processed_tweets.json`。[GitHub 文件写入 API 说明](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents)

如果组织策略或默认分支保护规则禁止工作流直接写入，状态保存会失败，并在发送邮件前停止。建议按本教程使用新建的个人专用仓库；不要为此修改其他项目的保护规则。

## 五、先测试，再启动

打开仓库 `Actions` → 左侧 `Codex Monitor` → `Run workflow`。如果 GitHub 提示启用 Actions，先点击启用。

依次运行：

1. **`test-email`**：只发送一封 85 分测试邮件，检查 QQ 收件箱。邮件原文明确标注“测试邮件”。测试不读取 RSS，也不修改去重记录。每次手动运行这个模式都会发一封。
2. **`preview`**：实际读取 RSS 并打印评分，验证 GitHub 云端是否能获取 Tibo 动态。此模式不发邮件、不写状态。应看到“取得 N 条，最新时间……”以及推文 ID、时间和链接。
3. **`monitor`**：正式读取、判断、发信并保存去重状态。没有达到 60 分的新信号时不发邮件，这是正常情况。

每次点开运行记录，查看 `Run monitor` 日志。绿色表示程序正常完成；`sent` 表示 QQ SMTP 已接受邮件，最终是否到达收件箱需要实际查看。必要时检查垃圾邮件。

工作流文件进入默认分支并启用 Actions 后，定时任务即生效，不需要电脑常开。计划为每小时第 **17 分钟** 执行一次，例如北京时间 10:17、11:17；GitHub 默认按 UTC 解释 cron，每小时的分钟数不受八小时时差影响。避开整点是为了减少排队影响。

GitHub 调度可能延迟或漏掉排队任务，不保证准点。公开仓库连续 60 天没有活动时，定时工作流可能被自动停用，需要到 Actions 重新启用。源码中的状态更新不是长期调度可用性的保证。[GitHub 定时触发说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## 免费 RSS 来源与实测

已内置主、备用来源：

- [主来源：nitter.privacyredirect.com](https://nitter.privacyredirect.com/thsottiaux/rss)
- [备用来源：nitter.kareem.one](https://nitter.kareem.one/thsottiaux/rss)

2026-09-14 在开发环境实测，两个来源均能解析出 **19 条 Tibo 动态**，最新条目时间为 `2026-09-12T08:09:17+00:00`。这是 RSS 返回内容的验证，并不能证明它与 X 的实时完整时间线一致，也尚未证明 GitHub 托管运行器能访问；请执行上面的 `preview` 完成云端验证。

Nitter 官方说明 RSS 是否开放取决于实例，可能因滥用被关闭。[项目说明](https://github.com/zedeus/nitter)和[实例列表](https://github.com/zedeus/nitter/wiki/Instances)可用于寻找替换来源。本次检测中，RSSHub 的 `twitter/user/thsottiaux` 路由返回 404，XCancel 返回 RSS 阅读器未获白名单许可，其他部分实例返回 403 或连接错误。

程序只请求已配置的免费 RSS：主来源连接失败、解析失败或没有有效 Tibo 推文时会尝试备用来源。全部失败时工作流报错，不会把错误页当作“没有重置信号”。不绕过验证码或白名单。可用 RSS 也可能存在延迟、截断或停止更新；日志会显示最新时间，请关注与实际情况是否一致。RSS 只提供有限条目，无法保证补齐长时间中断期间的所有动态。

## 判断规则

正文先检查是否明确包含 `Codex`，不区分大小写。没有提及 Codex 时不报警，因此只有“limits restored”的无上下文回复可能漏报。

| 类别 | 关键词 | 分数与类型 |
| --- | --- | --- |
| 高概率 | reset usage limits；usage limits restored；rate limits reset；limits restored；back to 100%；reset completed | 85，confirmed_reset |
| 疑似 | will reset；reset incoming；fixed an issue；investigating limits | 65，possible_reset |
| 普通 | 未命中有效规则 | 0，normal_update |

`fixed an issue` 所在句子还需要包含 limit、quota 或 reset。命中高概率关键词但含 will、soon、may 等未来或不确定表达时降为 65。包含常见否定词、疑问句的句子会跳过。邮件只在分数至少为 60 时发送。

分数是人工设定的规则强度，不是统计概率；confirmed_reset 是规则标签，不能证明个人账号已经获得重置。“AI分析”字段明确标注本地关键词规则，没有调用付费模型。规则无法完整理解引用、讽刺、复杂否定或其他上下文，仍可能误报或漏报。

## 邮件示例

标题：`🚨 Codex重置信号：85%`；疑似信号使用 `⚠️ Codex疑似重置：65%`。

```text
Codex重置信号：85%
判断：高概率重置，请到 Codex 额度页面确认实际状态。
====================

时间：2026-09-14T10:30:00+00:00
来源：Tibo (@thsottiaux)
原文链接：推文的 X 链接

原文：
Codex usage limits restored

信号类型：confirmed_reset

AI分析（本地关键词规则）：
命中 usage limits restored, limits restored。本结果来自关键词规则，分数不是统计概率。

建议：
建议立即打开 Codex 检查额度状态。
Codex小火车可能进站啦 🚂
```

## 去重与故障恢复

每次正式运行先从 GitHub 默认分支读取 `state/processed_tweets.json`。同一 tweet ID 已处理后不再发送；工作流串行执行，避免两次运行同时发信。首次运行只对过去 24 小时内的信号发信，历史动态标为 ignored，避免部署时批量提醒旧消息。初始化之后，所有本轮 RSS 中尚未记录的 ID 都会检查。

- `normal`：未达到发送阈值。
- `ignored`：首次运行跳过的历史条目。
- `pending`：发送前已保存的投递占位。
- `sent`：SMTP 已接受，最终状态已保存。

明确的 SMTP 拒绝或登录失败会释放该 ID，下次仍在 RSS 中时可重试。提交阶段断线、运行被中止，或 SMTP 成功后 GitHub 保存失败，可能留下 pending。此时程序暂停该 ID 的自动重发并报告失败，避免重复提醒；其他新动态仍可处理。SMTP 和 GitHub 无法保证跨服务严格“只投递一次”。

遇到 pending：先查看收件箱，根据推文链接核对是否已收到。然后在 GitHub 打开 `state/processed_tweets.json`，点击编辑：已收到则将对应 ID 的值从 `pending` 改为 `sent`；确认未收到且希望重试，则只删除该 ID 对应的一项，保持 JSON 语法正确，再运行 monitor。不要删除整个状态文件，否则会丢失去重记录。若该动态已滚出 RSS，删除 ID 后也无法自动重新获取它。

状态文件只存 ID 和状态，公开仓库中任何人可以查看。记录保存到仓库而非临时运行器，且保留所有已处理 ID；超长期运行接近 GitHub Contents API 文件大小限制时需维护状态存储。[Contents API 限制](https://docs.github.com/en/rest/repos/contents#get-repository-content)

## 开发与验证（可选，不影响云端运行）

在项目目录执行：

```text
python --version
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python main.py --mode preview
```

无第三方依赖，安装依赖命令可跳过。每次 Actions 运行也会先执行离线测试。测试使用模拟 SMTP 和 GitHub 状态，不会发送真实邮件或修改仓库。

`python main.py --mode test-email` 需要通过环境变量设置三个邮箱值。`monitor` 还需要 GitHub 提供的 GITHUB_TOKEN、GITHUB_REPOSITORY 和 STATE_BRANCH，日常使用请直接通过 Actions 执行。

本次开发验证：22 项离线测试通过；两个默认 RSS 来源开发环境读取成功。正式预览命令通过备用来源取得 19 条动态，均未达到提醒阈值。Python 3.10 语法解析检查通过；实际测试使用 Python 3.11。真实 QQ 收信、GitHub Actions 调度和仓库状态写入需要在你自己的仓库配置 Secrets 后验证。
