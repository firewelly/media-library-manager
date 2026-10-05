#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JavBus 单番号爬虫（Playwright）
Playwright 版使用固定持久会话(.playwright_user_data_javbus)保存年龄确认/语言等状态
输出 JSON 字段与历史版本一致: number/title/studio/release_date/actors/cover_image_url/cover_image_path/magnet_links
"""

import sys
import os
import time
import random
import logging
import json
from contextlib import suppress

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

try:
    from config import SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, USE_SOCKS5_PROXY
except Exception:
    SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT, USE_SOCKS5_PROXY = "127.0.0.1", 1080, True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 统一封面保存目录到 results/images（与其它脚本保持一致）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.join(BASE_DIR, 'results', 'images')
os.makedirs(COVERS_DIR, exist_ok=True)

# ==================== Playwright 版（优先） ====================
JAVBUS_BASE_SITES = ["https://www.javbus.com"]
JAVBUS_PW_USER_DATA_DIR = os.path.join(BASE_DIR, '.playwright_user_data_javbus', 'msedge')


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _random_delay(a, b):
    time.sleep(random.uniform(a, b))


def _setup_javbus_playwright(use_proxy=True, headless=False):
    """启动 JavBus 专用 Edge 持久会话（保存年龄确认/语言等 cookie 状态）"""
    if sync_playwright is None:
        return None
    proxy = None
    if use_proxy:
        proxy = {"server": f"socks5://{SOCKS5_PROXY_HOST}:{SOCKS5_PROXY_PORT}"}
    os.makedirs(JAVBUS_PW_USER_DATA_DIR, exist_ok=True)
    kwargs = {
        "headless": headless,
        "locale": "zh-CN",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "extra_http_headers": {"Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7"},
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--lang=zh-CN",
        ],
    }
    if proxy:
        kwargs["proxy"] = proxy
    pw = ctx = None
    try:
        pw = sync_playwright().start()
        ctx = pw.chromium.launch_persistent_context(JAVBUS_PW_USER_DATA_DIR, channel="msedge", **kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'ja', 'en'] });
        """)
        return {"pw": pw, "context": ctx, "page": page}
    except Exception as e:
        _log(f"[DEBUG] JavBus Playwright 启动失败: {e}")
        with suppress(Exception):
            if ctx:
                ctx.close()
        with suppress(Exception):
            if pw:
                pw.stop()
        return None


def _close_javbus_playwright(session):
    if not session:
        return
    with suppress(Exception):
        session["context"].close()
    with suppress(Exception):
        session["pw"].stop()


def _is_cloudflare_pw(page):
    try:
        title = (page.title() or "").lower()
        if "just a moment" in title or "attention required" in title:
            return True
        html = (page.content() or "").lower()
        return "cdn-cgi/challenge-platform" in html
    except Exception:
        return False


def _has_age_gate_pw(page):
    try:
        return page.locator("#enter-alert, #warning").count() > 0
    except Exception:
        return False


def _dismiss_age_gate_pw(page):
    for sel in ["#enter-alert a#enter", "a#enter", "#warning a", "a:has-text('是')", "a:has-text('Enter')"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                _random_delay(1, 2)
                if not _has_age_gate_pw(page):
                    _log(f"已自动通过年龄确认: {sel}")
                    return True
        except Exception:
            continue
    return False


def _is_404_pw(page):
    try:
        title = (page.title() or "").lower()
        if "404" in title:
            return True
        html = (page.content() or "").lower()
        return "404 page not found" in html[:3000]
    except Exception:
        return False


def _parse_javbus_detail_pw(page, url, av_code, context):
    """解析 JavBus 详情页（无有效标题返回 None）"""
    result = {
        "number": av_code,
        "title": "",
        "studio": "",
        "release_date": "",
        "actors": [],
        "cover_image_url": "",
        "cover_image_path": None,
        "magnet_links": [],
        "tags": [],
    }
    try:
        result["title"] = (page.locator("h3").first.text_content() or "").strip()
    except Exception:
        pass
    if not result["title"] or _is_404_pw(page):
        return None
    with suppress(Exception):
        result["studio"] = (page.locator("p:has(span:has-text('製作')) a").first.text_content() or "").strip()
    with suppress(Exception):
        t = page.locator("p:has(span:has-text('發行日期'))").first.text_content() or ""
        result["release_date"] = t.replace("發行日期:", "").replace("发行日期:", "").strip()
    with suppress(Exception):
        boxes = page.locator("#star-div .avatar-box")
        for i in range(boxes.count()):
            b = boxes.nth(i)
            name = ""
            with suppress(Exception):
                name = (b.locator("span").first.text_content() or "").strip()
            if not name:
                with suppress(Exception):
                    name = b.locator("img").first.get_attribute("title") or ""
            link = b.get_attribute("href") or ""
            if name:
                result["actors"].append({"name": name.strip(), "link": link})
    with suppress(Exception):
        src = page.locator("a.bigImage img").first.get_attribute("src") or ""
        if src:
            from urllib.parse import urljoin as _ujoin
            result["cover_image_url"] = _ujoin(url, src)
    if result["cover_image_url"]:
        with suppress(Exception):
            resp = context.request.get(result["cover_image_url"], headers={"Referer": url}, timeout=30000)
            if resp.ok:
                local_path = os.path.join(COVERS_DIR, f"{av_code}_cover.jpg")
                with open(local_path, "wb") as f:
                    f.write(resp.body())
                result["cover_image_path"] = local_path
    with suppress(Exception):
        magnets = page.eval_on_selector_all(
            '[data-clipboard-text^="magnet:?xt"]',
            "els => els.map(e => e.getAttribute('data-clipboard-text') || '').filter(Boolean)")
        for m in magnets:
            if m not in result["magnet_links"]:
                result["magnet_links"].append(m)
    with suppress(Exception):
        href_magnets = page.eval_on_selector_all(
            'a[href^="magnet:?xt"]',
            "els => els.map(e => e.getAttribute('href') || '').filter(Boolean)")
        for m in href_magnets:
            if m not in result["magnet_links"]:
                result["magnet_links"].append(m)
    with suppress(Exception):
        result["tags"] = page.eval_on_selector_all(
            "span.genre label",
            "els => els.map(e => (e.textContent || '').trim()).filter(Boolean)")
    return result


def _search_javbus_pw(page, site, av_code):
    """详情 URL 直连失败时走站内搜索，返回详情页 URL 或 None"""
    try:
        page.goto(f"{site}/search/{av_code}&type=0&parent=ce", wait_until="domcontentloaded", timeout=60000)
        _random_delay(1.5, 2.5)
        if _is_404_pw(page) or _is_cloudflare_pw(page):
            return None
        box = page.locator("a.movie-box").first
        if box.count() > 0:
            return box.get_attribute("href")
    except Exception:
        pass
    return None


def crawl_single_video_playwright(av_code):
    """Playwright 优先的 JavBus 爬虫（代理→直连，有界面→无头 逐级回退）"""
    if sync_playwright is None:
        _log("[WARN] Playwright 未安装，跳过 Playwright 流程")
        return None
    _log(f"[INFO] Starting Playwright crawl for JavBus code: {av_code}")
    for use_proxy in ([True, False] if USE_SOCKS5_PROXY else [False]):
        for headless in (False, True):
            session = _setup_javbus_playwright(use_proxy=use_proxy, headless=headless)
            if not session:
                continue
            page = session["page"]
            try:
                for site in JAVBUS_BASE_SITES:
                    url = f"{site}/{av_code}"
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    except Exception:
                        continue
                    _random_delay(1.5, 2.5)
                    if _is_cloudflare_pw(page):
                        if headless:
                            break
                        _log("检测到 Cloudflare 验证页，等待通过（最多120秒）...")
                        cleared = False
                        for _ in range(60):
                            if not _is_cloudflare_pw(page):
                                cleared = True
                                break
                            time.sleep(2)
                        if not cleared:
                            continue
                    if _has_age_gate_pw(page) and not _dismiss_age_gate_pw(page):
                        if headless:
                            break
                        for _ in range(30):
                            if not _has_age_gate_pw(page):
                                break
                            time.sleep(2)
                    parsed = _parse_javbus_detail_pw(page, url, av_code, session["context"])
                    if parsed:
                        return parsed
                    found = _search_javbus_pw(page, site, av_code)
                    if found:
                        try:
                            page.goto(found, wait_until="domcontentloaded", timeout=60000)
                            _random_delay(1.5, 2.5)
                        except Exception:
                            continue
                        if _has_age_gate_pw(page):
                            _dismiss_age_gate_pw(page)
                        parsed = _parse_javbus_detail_pw(page, found, av_code, session["context"])
                        if parsed:
                            return parsed
            except Exception as e:
                _log(f"[WARN] JavBus Playwright 异常: {e}")
            finally:
                _close_javbus_playwright(session)
    return None


def crawl_single_video(av_code):
    """统一入口：Playwright"""
    result = crawl_single_video_playwright(av_code)
    if result:
        result["success"] = True
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python javbus_crawler_single.py <video_code>")
        print("Example: python javbus_crawler_single.py CWPBD-89")
        sys.exit(1)
    
    av_code = sys.argv[1]
    result = crawl_single_video(av_code)
    
    if result and result['success']:
        # JSON格式输出
        json_result = {
            'number': result['number'],
            'title': result['title'],
            'studio': result['studio'],
            'release_date': result['release_date'],
            'actors': result['actors'],
            'tags': result.get('tags', []),
            'cover_image_url': result['cover_image_url'],
            'cover_image_path': result['cover_image_path'],
            'magnet_links': result['magnet_links']
        }
        print(json.dumps(json_result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"error": "Failed to crawl video information"}, ensure_ascii=False, indent=2))
        sys.exit(1)