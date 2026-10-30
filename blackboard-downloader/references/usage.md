# 上游运行与接口

源码核对日期：2026-09-29。核对版本：`b303200c053cdba2bd89b31209e9b27fc2e92e28`。
上游：https://github.com/aCm1T/BB-BlackBoard-Content-Downloader （MIT）。本 skill 提供工作流，不捆绑上游源码。升级后重新核对接口与行为；不要自动重置用户已有修改。

## 初次准备

使用固定缓存，而不是在每个任务目录新建下载器。默认布局：

```text
$HOME/Documents/Codex/.cache/blackboard-downloader/
  sites/https-bb.cuhk.edu.cn/
    runtime/              # 上游仓库、.venv、.env、cookies.json
    drivers/              # Selenium 驱动缓存
```

`BB_DOWNLOADER_HOME` 可覆盖缓存根目录。site-key 由规范化 origin 生成：小写 scheme、主机名和非默认端口，例如 `https-bb.cuhk.edu.cn`、`https-bb.example.edu-8443`。仅接受无用户信息、无查询/片段的 HTTP(S) 站点根地址，路径须为空或 `/`；路径、课程名和当前工作目录不参与缓存键。同一站点的不同账号若需保留独立会话，使用不同的 `BB_DOWNLOADER_HOME`。

每次运行先解析缓存和本次绝对输出目录，再进入固定 runtime。下面是 CUHK-Shenzhen 示例；其他站点替换 base URL 和 site-key：

```bash
umask 077
bb_cache_root="${BB_DOWNLOADER_HOME:-$HOME/Documents/Codex/.cache/blackboard-downloader}"
bb_site_dir="$bb_cache_root/sites/https-bb.cuhk.edu.cn"
bb_runtime="$bb_site_dir/runtime"
mkdir -p "$bb_site_dir/drivers"
chmod 700 "$bb_cache_root" "$bb_cache_root/sites" "$bb_site_dir" "$bb_site_dir/drivers"
export BB_BASE_URL='https://bb.cuhk.edu.cn'
export SE_CACHE_PATH="$bb_site_dir/drivers"
export WDM_LOCAL=1
```

**仅首次缺失时**，将上游克隆到 `$bb_runtime`，创建其 `.venv` 并安装 requirements；已有目录时核对版本、依赖后直接复用，不自动重置或升级，也不因当前任务目录改变而重建。

```bash
git clone https://github.com/aCm1T/BB-BlackBoard-Content-Downloader.git "$bb_runtime"
python3 -m venv "$bb_runtime/.venv"
"$bb_runtime/.venv/bin/python" -m pip install -r "$bb_runtime/requirements.txt"
```

默认复用缓存执行，不能无条件添加 `--relogin`。Python 至少 3.10；首次或会话真实失效时需要 Chrome/Edge 和图形会话，由用户完成校园登录/MFA。新任务可以直接使用有效的缓存。网络、DNS、TLS 失败与会话失效分开诊断；上游 `_validate_session()` 会将异常返回 False，遇到连接故障应先做无浏览器诊断，避免误触发登录。

上游 `.env`、`cookies.json` 均位于固定 runtime，环境变量优先于 `.env`。从旧任务迁移时先检查 base URL 及 Cookie 域匹配，且只在新位置没有 Cookie 时复制，保留旧原件；不得打印 Cookie 值。用 `chmod 600` 保护 Cookie，父目录权限 700；保持缓存根目录被版本控制忽略。下载完成后保留此缓存，打包时只收集本次课件目录。

上游默认下载目录是仓库内 `downloads/`，因此所有下载必须用 `-o` 或 `download_dir` 指定用户本次要求的绝对目录，不把课件放进共享缓存。

## 整课 CLI

```bash
.venv/bin/python main.py -c 'EXACT-COURSE-KEYWORD' -o '/absolute/output/path'
```

`-c` 是课程名/显示课程编号的不区分大小写子串匹配，不是内部 ID 精确选择。先核对匹配范围。`--relogin` 忽略缓存重新登录；`--all` 选择全部课程。没有 `--content-id`、`--dry-run` 或自动 ZIP 选项。

## 元数据检查与精确选择

以下代码在固定 runtime 目录、虚拟环境及已设置的站点环境中执行。只初始化会话与列出课程，不下载附件：

```python
from auth import get_session
from api import BlackboardAPI

session = get_session()
api = BlackboardAPI(session)
user = api.get_current_user()
for membership in api.get_user_courses(user['id']):
    course = api.get_course(membership['courseId'])
    print(course.get('id'), course.get('courseId'), course.get('name'))
```

课程确认后，`api.get_course_contents(course_id)` 列出顶层内容；`api.get_content_children(course_id, content_id)` 递归列出子内容；`api.get_content_attachments(course_id, content_id)` 列出附件。这些列表方法处理分页，但不能据空列表推断请求成功。

内容页链接可通过 `urllib.parse.urlparse` 和 `parse_qs` 读取 `course_id`、`content_id`。用以下直接 GET 验证指定内容，避免上游 `_get()` 将 403/404 转成空列表；核验标题符合用户目标后才执行下载：

```python
# course_id/content_id 来自当前用户目标并已核对，不填历史固定值。
from config import API_TIMEOUT
from downloader import CourseDownloader

response = session.get(
    f'{api.base_url}/courses/{course_id}/contents/{content_id}',
    timeout=API_TIMEOUT,
)
response.raise_for_status()
content = response.json()
if content.get('id') != content_id:
    raise RuntimeError('Content identity mismatch')
print(content['id'], content.get('title'))

# 完成范围及附件清单核对后执行：
dl = CourseDownloader(api, download_dir=output_dir)
# 对于非文件夹内容，先确保 output_dir 存在。
from pathlib import Path
Path(output_dir).mkdir(parents=True, exist_ok=True)
dl._process_content(course_id, content, str(output_dir))
dl.print_stats()
```

`_process_content` 接受内容对象而不是内容 ID 字符串。它会为文件夹创建子目录，但直接附件写入传入目录。精确整课调用是 `dl.download_course(course_id, course_name)`。

## 已核实的覆盖与陷阱

- 递归文件夹类型：`resource/x-bb-folder`、`resource/x-bb-lesson`、`resource/x-bb-coursemodule`。
- 附件类型：`resource/x-bb-document`、`resource/x-bb-file`、`resource/x-bb-assignment`、`resource/x-bb-asn-assignment` 以及缺少 handler 的内容。处理 assignment 类型只是读取附件，不提交作业。
- `api._get()` 将 403/404 转成空结果；子内容/附件枚举异常可能只打印警告或直接返回。需要严格清单时，枚举请求使用 `session.get()` 和 `raise_for_status()`，继续跟随分页直到结束；只跟随同站点 API URL，不记录敏感请求头。
- 上游会优先采用 `Content-Disposition` 文件名，且没有完整支持各种编码格式；清单应记录实际路径，避免按 API 文件名错误统计。
- 同名下载增加数字后缀；中断重试可能留下部分文件。不要按目录文件数量判定完整性，也不要自动删除用户旧文件。
- 增量跳过仅检查 API 声明大小大于零且与已有文件一致；同大小内容变更可能漏掉。需要确认最新版时单独重新下载比较。
- CLI 下载结束无条件显示完成提示，不能作为完整性证据。
