import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright

logger = logging.getLogger(__name__)

class PlaywrightController:
    """
    Playwright browser controller with network sniffer, console capture,
    semantic DOM extractor, and screenshot manager.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 15000, slow_mo: int = 0):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.slow_mo = slow_mo
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self.network_logs: List[Dict[str, Any]] = []
        self.console_logs: List[Dict[str, Any]] = []
        self.page_errors: List[Dict[str, Any]] = []

    def start(self):
        """Initializes the browser and hooks network/console listeners."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 AitestyExplorer/1.0",
            ignore_https_errors=True,
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout_ms)

        # Hook network request listener
        def on_request(req):
            self.network_logs.append({
                "type": "request",
                "timestamp": datetime.utcnow().isoformat(),
                "method": req.method,
                "url": req.url,
                "resource_type": req.resource_type,
                "has_post_data": bool(req.post_data),
            })

        # Hook network response listener
        def on_response(res):
            body_preview = ""
            try:
                # Capture preview for text/json responses
                content_type = res.headers.get("content-type", "")
                if "json" in content_type or "text" in content_type:
                    text = res.text()
                    body_preview = text[:400] + ("..." if len(text) > 400 else "")
            except Exception:
                pass

            self.network_logs.append({
                "type": "response",
                "timestamp": datetime.utcnow().isoformat(),
                "status": res.status,
                "status_text": res.status_text,
                "url": res.url,
                "ok": res.ok,
                "content_type": res.headers.get("content-type", ""),
                "body_preview": body_preview,
            })

        # Hook console listener
        def on_console(msg):
            self.console_logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": msg.type,
                "text": msg.text,
            })

        # Hook page error listener
        def on_page_error(err):
            self.page_errors.append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": str(err),
            })

        self.page.on("request", on_request)
        self.page.on("response", on_response)
        self.page.on("console", on_console)
        self.page.on("pageerror", on_page_error)

    def stop(self):
        """Closes page, context, browser, and playwright instance."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error while stopping PlaywrightController: {e}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def navigate(self, url: str) -> Dict[str, Any]:
        """Navigates to URL and returns status, final URL, and title."""
        if not self.page:
            raise RuntimeError("Browser not started")
        
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        status = response.status if response else 200
        title = self.page.title()
        current_url = self.page.url

        return {
            "status": status,
            "title": title,
            "url": current_url,
            "success": status < 400,
        }

    def click(self, selector: str) -> Dict[str, Any]:
        """Clicks an element by selector or visible text."""
        if not self.page:
            raise RuntimeError("Browser not started")
        
        # Try direct selector first, or text match
        if not selector.startswith("/") and not selector.startswith("#") and not selector.startswith("."):
            loc = self.page.locator(selector).or_(self.page.get_by_text(selector, exact=False)).first
            loc.click(timeout=5000)
        else:
            self.page.click(selector, timeout=5000)

        # Allow slight delay for microtasks / re-renders
        self.page.wait_for_timeout(300)
        return {"success": True, "action": "click", "selector": selector, "new_url": self.page.url}

    def fill(self, selector: str, value: str) -> Dict[str, Any]:
        """Fills an input field."""
        if not self.page:
            raise RuntimeError("Browser not started")
        
        self.page.fill(selector, value, timeout=5000)
        return {"success": True, "action": "fill", "selector": selector}

    def select_option(self, selector: str, value: str) -> Dict[str, Any]:
        """Selects an option from a <select> dropdown."""
        if not self.page:
            raise RuntimeError("Browser not started")
        try:
            self.page.select_option(selector, value=value, timeout=5000)
            self.page.wait_for_timeout(300)
            return {"success": True, "action": "select", "selector": selector, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scroll(self, direction: str = "down", amount: int = 600) -> Dict[str, Any]:
        """Scrolls the page to reveal lazy-loaded elements or footer navigation."""
        if not self.page:
            raise RuntimeError("Browser not started")
        delta = amount if direction.lower() == "down" else -amount
        self.page.evaluate(f"window.scrollBy(0, {delta});")
        self.page.wait_for_timeout(400)
        return {"success": True, "action": "scroll", "direction": direction, "amount": amount}

    def wait(self, milliseconds: int = 500):
        if self.page:
            self.page.wait_for_timeout(milliseconds)

    def extract_crawl_targets(self, allowed_domain: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Extracts all clean, same-origin, navigable URLs from the active page.
        Resolves relative URLs, strips hash fragments, and filters out non-navigable
        links (downloads, media, auth logout triggers, mailto).
        """
        if not self.page:
            return []

        script = """(allowedHost) => {
            const currentOrigin = window.location.origin;
            const currentHost = allowedHost || window.location.hostname;
            const skipExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf', '.zip', '.tar', '.gz', '.css', '.js', '.woff', '.woff2', '.mp4'];
            const dangerousKeywords = ['logout', 'signout', 'delete-account', 'delete_account', 'reset-password'];

            const links = Array.from(document.querySelectorAll('a[href]'));
            const results = [];
            const seen = new Set();

            for (const a of links) {
                let href = a.getAttribute('href');
                if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) {
                    continue;
                }

                let fullUrl;
                try {
                    fullUrl = new URL(href, window.location.href);
                } catch (e) {
                    continue;
                }

                // Check host / domain
                if (fullUrl.hostname !== currentHost && !fullUrl.hostname.endsWith('.' + currentHost)) {
                    continue;
                }

                // Remove hash fragment and search params that are volatile
                fullUrl.hash = '';
                const cleanUrl = fullUrl.href;

                // Check skip extensions
                const pathname = fullUrl.pathname.toLowerCase();
                if (skipExtensions.some(ext => pathname.endsWith(ext))) {
                    continue;
                }

                // Check dangerous keywords
                if (dangerousKeywords.some(kw => pathname.includes(kw))) {
                    continue;
                }

                if (seen.has(cleanUrl)) {
                    continue;
                }
                seen.add(cleanUrl);

                const text = (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim().substring(0, 50);
                const isNav = Boolean(a.closest('nav, header, [role="navigation"], .navbar, .menu, .sidebar'));

                results.push({
                    url: cleanUrl,
                    path: fullUrl.pathname,
                    text: text || fullUrl.pathname,
                    is_nav: isNav
                });
            }
            return results;
        }"""
        try:
            domain_arg = allowed_domain or ""
            targets = self.page.evaluate(script, domain_arg)
            return targets if isinstance(targets, list) else []
        except Exception as e:
            logger.warning(f"Error extracting crawl targets: {e}")
            return []

    def take_screenshot(self, save_path: str) -> str:
        """Captures viewport screenshot and saves to save_path."""
        if not self.page:
            raise RuntimeError("Browser not started")
        path_obj = Path(save_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path_obj), full_page=False)
        return str(path_obj)

    def get_dom_summary(self) -> Dict[str, Any]:
        """
        Extracts visible semantic structure:
        - Active URL and page title
        - Interactive elements (buttons, inputs, links with paths)
        - Headings and alert messages
        """
        if not self.page:
            return {"error": "Browser not initialized"}

        # Run client-side extraction script for clean token-efficient representation
        script = """() => {
            const isVisible = (el) => {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0 && el.offsetHeight > 0;
            };

            const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
                .filter(isVisible)
                .slice(0, 15)
                .map(el => ({
                    tag: el.tagName.toLowerCase(),
                    name: el.name || el.id || '',
                    type: el.type || 'text',
                    placeholder: el.placeholder || '',
                    selector: el.id ? `#${el.id}` : (el.name ? `input[name='${el.name}']` : el.tagName.toLowerCase())
                }));

            const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'))
                .filter(isVisible)
                .slice(0, 15)
                .map(el => ({
                    text: (el.innerText || el.value || '').trim().substring(0, 40),
                    selector: el.id ? `#${el.id}` : `button:has-text("${(el.innerText || '').trim().substring(0, 20)}")`
                }));

            const links = Array.from(document.querySelectorAll('a[href]'))
                .filter(isVisible)
                .slice(0, 20)
                .map(el => ({
                    text: (el.innerText || '').trim().substring(0, 30),
                    href: el.getAttribute('href') || ''
                }))
                .filter(l => l.text.length > 0 && !l.href.startsWith('javascript:'));

            const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                .filter(isVisible)
                .slice(0, 8)
                .map(el => el.innerText.trim());

            const alerts = Array.from(document.querySelectorAll('.alert, .error, [role="alert"]'))
                .filter(isVisible)
                .map(el => el.innerText.trim());

            const forms = Array.from(document.querySelectorAll('form'))
                .filter(isVisible)
                .slice(0, 5)
                .map(f => ({
                    id: f.id || '',
                    action: f.getAttribute('action') || '',
                    method: (f.getAttribute('method') || 'GET').toUpperCase(),
                    inputCount: f.querySelectorAll('input, select, textarea').length
                }));

            return {
                headings,
                inputs,
                buttons,
                links,
                alerts,
                forms
            };
        }"""
        try:
            dom_data = self.page.evaluate(script)
        except Exception as e:
            dom_data = {"error": str(e)}

        return {
            "url": self.page.url,
            "title": self.page.title(),
            "dom": dom_data,
        }

    def get_recent_network(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns the most recent network calls."""
        return self.network_logs[-limit:]

    def get_recent_console(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent console messages."""
        return self.console_logs[-limit:]

    def dump_network_traffic(self, file_path: str):
        """Saves all intercepted network requests and responses as JSON."""
        path_obj = Path(file_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            json.dump({
                "total_events": len(self.network_logs),
                "events": self.network_logs,
                "console_errors": self.page_errors,
            }, f, indent=2)
