from __future__ import annotations

from pathlib import Path

import pytest

from jobscout.sites.zhipin import (
    build_search_url,
    extract_job_id,
    parse_job_detail_from_html,
    parse_salary,
    resolve_city_code,
)
from jobscout.config import CrawlConfig

FIXTURE = Path(__file__).parent / "fixtures" / "zhipin_job_detail_sample.html"


def test_extract_job_id_basic():
    assert extract_job_id("/job_detail/abc123def.html") == "abc123def"
    assert extract_job_id("https://www.zhipin.com/job_detail/x9y8.html?k=v") == "x9y8"
    assert extract_job_id("/some/other/path") is None


def test_parse_salary_kilo():
    assert parse_salary("20-35K·14薪") == (20, 35)
    assert parse_salary("15-25k") == (15, 25)
    assert parse_salary("不限") == (None, None)
    assert parse_salary(None) == (None, None)


def test_parse_salary_wan_unit_converts_to_thousands():
    # 1万 = 10K thousand-yuan; "1-2万" -> (10, 20)
    assert parse_salary("1-2万") == (10, 20)


def test_resolve_city_code_known():
    assert resolve_city_code("Beijing") == "101010100"
    assert resolve_city_code("北京") == "101010100"
    assert resolve_city_code("shanghai") == "101020100"


def test_resolve_city_code_numeric_passthrough():
    assert resolve_city_code("101010100") == "101010100"


def test_resolve_city_code_unknown_returns_none():
    assert resolve_city_code("Atlantis") is None
    assert resolve_city_code(None) is None


def test_build_search_url_minimal():
    cfg = CrawlConfig(keyword="Python")
    url = build_search_url(cfg)
    assert url.startswith("https://www.zhipin.com/web/geek/jobs?")
    assert "query=Python" in url


def test_build_search_url_with_city_and_filters():
    cfg = CrawlConfig(keyword="数据", city="Beijing", experience="104", salary="406")
    url = build_search_url(cfg)
    assert "city=101010100" in url
    assert "experience=104" in url
    assert "salary=406" in url


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture not yet captured; run with --debug-dump first")
def test_parse_job_detail_from_html_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    job = parse_job_detail_from_html(html, "https://www.zhipin.com/job_detail/sample.html", "sample")
    assert job.job_id == "sample"
    assert job.title and job.title != "(unknown title)"
    assert job.company and job.company != "(unknown company)"
