#!/usr/bin/env python3
"""
Cochrane Systematic Reviews MCP Server
使用 Europe PMC REST API（免费，无需认证）搜索 Cochrane 系统综述和临床试验。
"""

import re
from typing import Annotated, Optional

import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPMC_SEARCH_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
)
COCHRANE_JOURNAL_FILTER = 'JOURNAL:"Cochrane Database Syst Rev"'

# Reasonable timeout to avoid hanging
DEFAULT_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# FastMCP 实例
# ---------------------------------------------------------------------------

mcp = FastMCP("cochrane-mcp")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """去除 HTML 标签并合并多余空白。"""
    if not text:
        return ""
    text = _HTML_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_conclusions(abstract: str) -> Optional[str]:
    """从 Cochrane 摘要中提取 AUTHORS' CONCLUSIONS 段落。"""
    if not abstract:
        return None

    plain = _strip_html(abstract)

    patterns = [
        r"AUTHORS['’]?\s*CONCLUSIONS?:?\s*(.+?)(?=\n[A-Z]{2,}|$)",
        r"CONCLUSIONS?:?\s*(.+?)(?=\n[A-Z]{2,}|$)",
        r"Main results:?\s*(.+?)(?=\n[A-Z]{2,}|$)",
    ]

    for pat in patterns:
        m = re.search(pat, plain, re.DOTALL | re.IGNORECASE)
        if m:
            conclusion = m.group(1).strip()
            if len(conclusion) > 2000:
                conclusion = conclusion[:2000] + "..."
            return conclusion

    return None


def _parse_result(result: dict) -> dict:
    """将 EPMC 原始结果解析为统一格式。"""
    journal_info = result.get("journalInfo", {}) or {}
    journal = journal_info.get("journal", {}) or {}
    journal_title = journal.get("title", "") or result.get("journalTitle", "")

    return {
        "title": result.get("title", "N/A"),
        "pmid": result.get("pmid", result.get("id", "N/A")),
        "authorString": result.get("authorString", "N/A"),
        "journalTitle": journal_title or "Cochrane Database Syst Rev",
        "pubYear": result.get("pubYear", "N/A"),
        "doi": result.get("doi", "N/A"),
        "source": result.get("source", "N/A"),
        "citedByCount": result.get("citedByCount", 0),
        "pubType": result.get("pubTypeList", {}).get("pubType", []),
    }


async def _epmc_get(client: httpx.AsyncClient, params: dict) -> dict:
    """封装 EPMC API 调用与错误处理。"""
    resp = await client.get(
        EPMC_SEARCH_URL,
        params=params,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_cochrane_reviews(
    query: Annotated[str, "搜索关键词，例如 'COVID-19 corticosteroids'"],
    limit: Annotated[int, "返回结果数量上限，默认 20"] = 20,
) -> dict:
    """搜索 Cochrane 系统综述。

    通过 Europe PMC API 检索 Cochrane Database of Systematic Reviews 中的文献。
    结果包含 title, pmid, authorString, journalTitle, pubYear, doi, citedByCount，
    以及从摘要中提取的作者结论（authors' conclusions）。

    Args:
        query: 搜索关键词，支持 Boolean 语法（AND, OR, NOT）
        limit: 返回结果数量，默认 20，最大 100

    Returns:
        dict: {"total": 总数, "results": [综述列表], "query": 原始查询}
    """
    limit = max(1, min(limit, 100))

    # 构建查询：用户关键词 + 期刊过滤
    full_query = f'({query}) AND {COCHRANE_JOURNAL_FILTER}'

    params = {
        "query": full_query,
        "resultType": "core",
        "pageSize": limit,
        "format": "json",
    }

    async with httpx.AsyncClient() as client:
        data = await _epmc_get(client, params)

    result_list = data.get("resultList", {})
    results = result_list.get("result", [])
    total = int(result_list.get("hitCount") or 0) or result_list.get(
        "totalResults", len(results)
    )

    parsed = []
    for item in results:
        p = _parse_result(item)
        # 尝试提取 conclusions
        abstract = item.get("abstractText", "")
        conclusions = _extract_conclusions(abstract)
        p["authorsConclusions"] = conclusions

        if abstract:
            p["abstractSnippet"] = (
                _strip_html(abstract)[:500] + "..."
                if len(_strip_html(abstract)) > 500
                else _strip_html(abstract)
            )
        else:
            p["abstractSnippet"] = None

        parsed.append(p)

    return {
        "total": total,
        "returned": len(parsed),
        "query": query,
        "fullQuery": full_query,
        "results": parsed,
    }


@mcp.tool()
async def get_review_detail(
    pmid: Annotated[str, "PubMed ID (PMID)，例如 '35246815'"],
) -> dict:
    """获取单篇 Cochrane 综述的完整详情。

    返回完整的 abstractText, authorString, journalTitle, pubYear, doi, citedByCount，
    以及提取的作者结论（authorsConclusions）。

    Args:
        pmid: 要查询的综述 PMID

    Returns:
        dict: 包含完整详情的字典，或 error 信息
    """
    params = {
        "query": f"EXT_ID:{pmid} SRC:MED",
        "resultType": "core",
        "pageSize": 1,
        "format": "json",
    }

    async with httpx.AsyncClient() as client:
        data = await _epmc_get(client, params)

    result_list = data.get("resultList", {})
    results = result_list.get("result", [])

    if not results:
        return {
            "error": True,
            "message": f"未找到 PMID {pmid} 对应的文献。请确认 PMID 是否正确。",
        }

    item = results[0]
    parsed = _parse_result(item)

    abstract = item.get("abstractText", "")
    conclusions = _extract_conclusions(abstract)

    parsed["abstractText"] = abstract
    parsed["authorsConclusions"] = conclusions

    # 额外字段
    parsed["language"] = item.get("language", "N/A")
    parsed["pubModel"] = item.get("pubModel", "N/A")
    parsed["pageInfo"] = item.get("pageInfo", "N/A")
    parsed["issue"] = item.get("issue", "N/A")
    parsed["volume"] = item.get("volume", "N/A")
    parsed["hasPDF"] = item.get("hasPDF", "N")

    return {"detail": parsed}


@mcp.tool()
async def search_clinical_trials(
    condition: Annotated[str, "疾病或健康状况，例如 'type 2 diabetes'"],
    intervention: Annotated[
        Optional[str], "干预措施，例如 'metformin'。可选参数。"
    ] = None,
    limit: Annotated[int, "返回结果数量，默认 20"] = 20,
) -> dict:
    """搜索与指定疾病/干预相关的临床试验。

    通过 Europe PMC API 检索临床试验文献（PUB_TYPE: clinical trial），
    也可使用 SRC:CT 直接检索临床试验注册记录。

    Args:
        condition:  疾病或健康状况（必填）
        intervention: 干预措施（可选）
        limit: 返回结果数量，默认 20，最大 100

    Returns:
        dict: {"total": 总数, "results": [试验列表], "query": 查询条件摘要}
    """
    limit = max(1, min(limit, 100))

    # 构建查询
    query_parts = [f'("{condition}")']
    if intervention:
        query_parts.append(f'("{intervention}")')
    query_parts.append('PUB_TYPE:"clinical trial"')

    full_query = " AND ".join(query_parts)

    params = {
        "query": full_query,
        "resultType": "core",
        "pageSize": limit,
        "format": "json",
    }

    async with httpx.AsyncClient() as client:
        data = await _epmc_get(client, params)

    result_list = data.get("resultList", {})
    results = result_list.get("result", [])
    total = int(result_list.get("hitCount") or 0) or result_list.get(
        "totalResults", len(results)
    )

    parsed = []
    for item in results:
        p = _parse_result(item)
        abstract = item.get("abstractText", "")
        if abstract:
            p["abstractSnippet"] = (
                abstract[:500] + "..." if len(abstract) > 500 else abstract
            )
        else:
            p["abstractSnippet"] = None
        parsed.append(p)

    return {
        "total": total,
        "returned": len(parsed),
        "condition": condition,
        "intervention": intervention,
        "fullQuery": full_query,
        "results": parsed,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """MCP 服务器入口。"""
    mcp.run()


if __name__ == "__main__":
    main()
