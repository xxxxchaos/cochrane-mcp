# Cochrane MCP Server

[![PyPI](https://img.shields.io/badge/python-3.10+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-stdio-orange.svg)]()

基于 FastMCP 的 **Cochrane 系统综述搜索** MCP Server。通过 Europe PMC REST API 检索 Cochrane Database of Systematic Reviews，**免费，无需认证**。

## 功能

| 工具 | 说明 |
|------|------|
| `search_cochrane_reviews` | 搜索 Cochrane 系统综述，自动提取 authors' conclusions |
| `get_review_detail` | 获取单篇综述完整详情（摘要、作者、MeSH、结论）|
| `search_clinical_trials` | 搜索与疾病/干预相关的临床试验 |

## 快速开始

### 前提

- Python ≥ 3.10
- [uv](https://github.com/astral-sh/uv)

### MCP 客户端配置

**Claude Code / Claude Desktop** (`~/.claude.json` 或 `claude_desktop_config.json`)：

```json
{
  "mcpServers": {
    "cochrane": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/xxxxchao/cochrane-mcp",
        "cochrane-mcp"
      ]
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`)：

```json
{
  "mcpServers": {
    "cochrane": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/xxxxchao/cochrane-mcp",
        "cochrane-mcp"
      ]
    }
  }
}
```

### 本地开发

```bash
git clone https://github.com/xxxxchao/cochrane-mcp.git
cd cochrane-mcp
uv sync
uv run cochrane-mcp
```

## 使用示例

在 AI 助手中直接提问：

> 搜索 Cochrane 系统综述：sepsis corticosteroids

> 获取 PMID 40470636 的完整详情和结论

> 搜索 sepsis 相关的临床试验，干预措施为 corticosteroids

## API 说明

底层使用 [Europe PMC REST API](https://europepmc.org/RestfulWebService)：

- **搜索端点**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- **Cochrane 过滤**: `JOURNAL:"Cochrane Database Syst Rev"`
- **临床试验过滤**: `PUB_TYPE:"clinical trial"`
- 免费，无需 API Key，速率限制约 1 req/s

## 项目结构

```
cochrane-mcp/
├── cochrane_mcp_server.py   # MCP 服务主文件
├── pyproject.toml            # 项目配置与依赖
├── LICENSE                   # MIT
└── README.md
```

## License

MIT
