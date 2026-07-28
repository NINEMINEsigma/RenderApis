# RenderQuery — 开发文档

## 构建前提：获取 renderdoc Python 绑定

RenderQuery 依赖 `import renderdoc`（SWIG 生成的 Python 绑定）。这个绑定是 RenderDoc 构建过程的产物，不是 pip 包。

### Windows 构建方式

Windows 上 RenderDoc 不用 CMake（CMakeLists.txt 第 252 行明确报错阻止），直接用 MSBuild 构建 `renderdoc.sln`。

仓库自带 SWIG（`qrenderdoc/3rdparty/swig/`）和 Python 3.6 嵌入版（`qrenderdoc/3rdparty/python/`），不需要额外安装。

#### 一键构建脚本

```powershell
# 在 D:\RenderApis 根目录
# 必须指定 Visual Studio 路径
.\build.ps1 -VsPath "D:\VS2022"

# 如果要用自己的 Python 版本（而非仓库自带的 3.6）
.\build.ps1 -VsPath "D:\VS2022" -PythonPrefix "D:\Python312"

# 完整参数
.\build.ps1 -VsPath "D:\VS2022" -Configuration Release -Platform x64
```

`build.ps1` 参数说明：

| 参数 | 必填 | 说明 |
|---|---|---|
| `-VsPath` | 是 | Visual Studio 安装路径，脚本会在其中找 MSBuild |
| `-PythonPrefix` | 否 | 自定义 Python 路径（需含 `include\Python.h`、`libs\python3X.lib`、`python3X.zip`）。不传则用仓库自带的 Python 3.6 |
| `-Configuration` | 否 | `Release`（默认）或 `Debug` |
| `-Platform` | 否 | `x64`（默认）或 `Win32` |

构建完成后，脚本会输出 `_renderdoc.pyd` 和 `renderdoc.dll` 的路径。

#### 手动构建（不用脚本）

```powershell
# 定位 MSBuild
$msbuild = "D:\VS2022\MSBuild\Current\Bin\MSBuild.exe"

# 可选：使用自定义 Python（否则用仓库自带 3.6）
$env:RENDERDOC_PYTHON_PREFIX64 = "D:\Python312"

# 构建 renderdoc.dll + Python 绑定
& $msbuild "D:\RenderApis\renderdoc.sln" /t:renderdoc;pyrenderdoc_module /p:Configuration=Release /p:Platform=x64 /m /v:minimal
```

### 确认绑定可用

```powershell
# 构建产物通常在 build\Release\x64\ 或 x64\Release\ 下
# 用 build.ps1 会输出确切路径
set PYTHONPATH=<构建产物目录>

python -c "import renderdoc; print('OK')"
```

> **注意**：`_renderdoc.pyd` 依赖同目录下的 `renderdoc.dll`。确保两者在同一目录，或将该目录加入 PATH。

### 使用 renderquery（不需要安装）

renderquery 是纯 Python 包，不需要 `pip install`。直接用 PYTHONPATH 指向两个目录即可：

```powershell
# PYTHONPATH = renderdoc 构建产物目录 + renderquery 源码目录
set PYTHONPATH=<构建产物目录>;D:\RenderApis\renderquery

# 验证
python -c "import renderdoc; import renderquery; print('OK')"
```

如果使用 HTTP Server，需要额外安装 fastapi/uvicorn（装到你自己指定的 Python 环境中）：

```powershell
pip install fastapi uvicorn pydantic
```

---

## 使用方法

### 方式一：Python SDK（进程内直接调用）

```python
from renderquery.sdk import RenderQueryClient
from renderquery.engine import artifacts
import renderdoc as rd

# 打开 capture 文件
client = RenderQueryClient("test.rdc")

# 构建查询：耗时最长的前10% drawcall 的截图 + mesh
results = (client.query()
    .from_actions(flags=int(rd.ActionFlags.Drawcall))
    .with_gpu_counter(int(rd.GPUCounter.EventGPUDuration))
    .sort_by("duration_gpu", desc=True)
    .take_percent(10)
    .project(
        event_id="{event_id}",
        name="{name}",
        duration_gpu="{duration_gpu}",
        screenshot=artifacts.screenshot(width=512, height=512),
        mesh=artifacts.mesh(stage="PostVS"),
    )
    .to_file("./out/")
    .execute())  # .execute() 也可以换成 client.execute(query, "./out/")

for r in results:
    print(f"event {r['event_id']}: {r['duration_gpu']:.3f}us  "
          f"screenshot={r['screenshot']}  mesh={r['mesh']}")

# 显式持久化 GPU counter 缓存（可选）
client.save_index("./out/gpu_counters.json")

client.shutdown()
```

### 方式二：CLI（命令行 JSON 交互）

```powershell
# 确保 PYTHONPATH 指向 renderdoc 绑定
set PYTHONPATH=D:\RenderApis\build\qrenderdoc\Release

# 加载 capture
renderquery load test.rdc

# 执行查询（通过 stdin 传入 JSON plan）
echo {"source":{"kind":"actions","params":{"flags":2}},"steps":[{"op":"with_counter","params":{"counter":1}},{"op":"sort","params":{"field":"duration_gpu","desc":true}},{"op":"take_percent","params":{"pct":10}}],"projection":[{"name":"event_id","expr":"{event_id}"},{"name":"name","expr":"{name}"},{"name":"duration_gpu","expr":"{duration_gpu}"},{"name":"screenshot","expr":"screenshot","is_artifact":true,"artifact_params":{"width":512,"height":512}}],"output_dir":"./out/"} | renderquery query

# 查看状态
renderquery status

# 查看 schema
renderquery schema
```

也可以通过 `--plan` 直接传 JSON 字符串而不走 stdin：

```powershell
renderquery query --capture test.rdc --plan "{...}" --output-dir ./out/
```

### 方式三：HTTP Server

```powershell
# 启动服务器（默认 127.0.0.1:8080）
renderquery serve --host 0.0.0.0 --port 8080 --capture test.rdc
```

API 端点：

```bash
# 加载 capture
curl -X POST http://localhost:8080/capture/load \
  -H "Content-Type: application/json" \
  -d '{"path": "test.rdc"}'

# 执行查询
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "plan": {
      "source": {"kind": "actions", "params": {"flags": 2}},
      "steps": [
        {"op": "with_counter", "params": {"counter": 1}},
        {"op": "sort", "params": {"field": "duration_gpu", "desc": true}},
        {"op": "take_percent", "params": {"pct": 10}}
      ],
      "projection": [
        {"name": "event_id", "expr": "{event_id}"},
        {"name": "name", "expr": "{name}"},
        {"name": "duration_gpu", "expr": "{duration_gpu}"},
        {"name": "screenshot", "expr": "screenshot", "is_artifact": true,
         "artifact_params": {"width": 512, "height": 512}}
      ],
      "output_dir": "./out/"
    },
    "output_dir": "./out/"
  }'

# 查看状态
curl http://localhost:8080/status

# 查看 schema
curl http://localhost:8080/schema

# 持久化 GPU counter 缓存
curl -X POST http://localhost:8080/index/save \
  -H "Content-Type: application/json" \
  -d '{"path": "./out/counters.json"}'

# 加载缓存
curl -X POST http://localhost:8080/index/load \
  -H "Content-Type: application/json" \
  -d '{"path": "./out/counters.json"}'
```

**并发行为**：不排队。Executor 正在执行查询时，新的 `POST /query` 立即返回 `409 Conflict`。

---

## DSL 操作符参考

### 源操作

| 方法 | 说明 |
|---|---|
| `.from_actions(flags=None)` | 以 Action 为数据源，可选按 ActionFlags 过滤 |
| `.from_events()` | 以所有 event 为数据源 |
| `.from_resources()` | 以资源列表为数据源 |

### 变换步骤（按链顺序执行，不做隐式重排）

| 方法 | 说明 |
|---|---|
| `.with_gpu_counter(counter)` | 注入 GPU counter 数据（首次触发 FetchCounters，之后读缓存） |
| `.filter("expr > 1000")` | 按表达式过滤行 |
| `.sort_by("field", desc=False)` | 按字段排序 |
| `.take(n)` | 取前 N 行 |
| `.take_percent(pct)` | 取前 N% 行（基于当前行数） |
| `.group_by("field")` | 按字段分组（占位，后续聚合支持） |

### 投影

| 方法 | 说明 |
|---|---|
| `.project(event_id="{event_id}", ...)` | 元数据字段用模板字符串 |
| `.project(screenshot=artifacts.screenshot(512, 512))` | artifact 字段传 ArtifactSpec |

### 输出

| 方法 | 说明 |
|---|---|
| `.to_file("./out/")` | 设置 artifact 输出目录 |
| `.compile()` | 编译为 QueryPlan IR（JSON 可序列化） |
| `.execute()` | 编译 + 执行（SDK 链式终端） |

---

## Artifact 类型

| 函数 | 产出 | 说明 |
|---|---|---|
| `artifacts.screenshot(w, h)` | `.png` 文件 | 当前输出目标的截图 |
| `artifacts.mesh(stage="PostVS")` | `.obj` 文件 | Post-VS 顶点数据 |
| `artifacts.texture_data(rid, ...)` | `.dds` 文件 | 原始纹理数据 |
| `artifacts.shader_disasm(stage="Vertex")` | `.txt` 文件 | shader 反汇编 |
| `artifacts.buffer_data(rid, offset, len)` | `.bin` 文件 | 原始缓冲区数据 |

所有 artifact 保存为文件，结果行中对应字段的值是文件路径。

---

## 缓存策略

| 层级 | 内容 | 生命周期 |
|---|---|---|
| L0 | actions, chunks, resources, textures, buffers | Catalog 初始化时加载，会话常驻 |
| L1 | gpu_counters, resource_usage | 首次访问时计算，会话内复用 |
| L2 | 导出的 JSON 索引文件 | 跨会话，需显式 `save_index()` / `load_index()` |

默认不跨查询复用 L1 缓存。除非显式保存到文件并在下次会话中加载。

---

## 可用字段

运行 `renderquery schema` 或访问 `GET /schema` 获取完整列表。核心字段：

```
event_id, action_id, parent_id, name, custom_name, flags,
num_indices, num_instances, duration_cpu, duration_gpu,
outputs, depth_out, draw_index, dispatch_dimension
```

---

## 包结构

```
renderquery/
  pyproject.toml
  renderquery/
    engine/
      catalog.py       # 元数据加载 + L0/L1/L2 缓存
      plan.py          # QueryPlan IR (JSON 可序列化)
      dsl.py           # 链式 DSL 构建器
      executor.py      # 单线程执行器 + 游标管理 + artifact 调度
      artifacts.py     # artifact 描述符
    sdk/
      client.py        # Python SDK (RenderQueryClient)
    server/
      cli.py           # CLI 前端
      http_server.py   # HTTP Server 前端 (FastAPI)
    examples/
      top10_gpu_drawcall_screenshots.py
```