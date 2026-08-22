import json
import logging
import sys
import time
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

class RateLimitError(Exception):
    pass

class TargetPrivateError(Exception):
    pass


def scrape_readonly(profile_url: str, cookies: str = None) -> dict:
    scraped_data = {
        "username": "@" + profile_url.split("?")[0].rstrip("/").split("/")[-1],
        "bio": "",
        "posts": [],
        "post_times": [],
        "images": []
    }

    def intercept_response(response):
        try:
            if "graphql" not in response.url:
                return
            if response.request.method == "OPTIONS":
                return

            if response.status == 429:
                raise RateLimitError("X (Twitter) Rate Limit'e (429) takildik.")
            if response.status == 403:
                raise RateLimitError("X (Twitter) Erisim Reddedildi (403). Cookie suresi dolmus olabilir.")

            try:
                resp_json = response.json()
            except Exception as exc:
                logger.error("GraphQL JSON parse failed for %s: %s", response.url, exc)
                raise

            if "UserByScreenName" in response.url:
                legacy = resp_json.get("data", {}).get("user", {}).get("result", {}).get("legacy", {})
                if legacy.get("protected"):
                    raise TargetPrivateError("Hedef hesap gizli (Protected). Icerik kazinamiyor.")
                bio = legacy.get("description", "")
                if bio:
                    scraped_data["bio"] = bio

            elif "UserTweets" in response.url:
                instructions = resp_json.get("data", {}).get("user", {}).get("result", {}).get("timeline_v2", {}).get("timeline", {}).get("instructions", [])
                for instr in instructions:
                    if instr.get("type") != "TimelineAddEntries":
                        continue
                    for entry in instr.get("entries", []):
                        if "tweet" not in entry.get("entryId", ""):
                            continue
                        legacy = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {}).get("legacy", {})
                        if not legacy:
                            continue
                        text = legacy.get("full_text", "")
                        if text:
                            scraped_data["posts"].append(text.replace("\n", " "))
                        created_at = legacy.get("created_at", "")
                        if created_at:
                            scraped_data["post_times"].append(created_at)
                        for media in legacy.get("entities", {}).get("media", []):
                            if media.get("type") == "photo":
                                scraped_data["images"].append(media.get("media_url_https", ""))

        except (RateLimitError, TargetPrivateError):
            raise
        except Exception:
            logger.exception("Unhandled GraphQL response processing failure")
            raise

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        if cookies:
            parsed = []
            for part in cookies.split(";"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    parsed.append({"name": k.strip(), "value": v.strip(), "domain": ".x.com", "path": "/"})
            if parsed:
                try:
                    ctx.add_cookies(parsed)
                except Exception:
                    logger.exception("Cookie injection failed")
                    raise

        page = ctx.new_page()
        page.on("response", intercept_response)
        page.goto(profile_url, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)
        browser.close()

        if "error" in scraped_data:
            raise scraped_data["error"]
        if not scraped_data["bio"] and not scraped_data["posts"]:
            raise RuntimeError("InsufficientEvidenceError: X profili tamamen bos veya veri cekilemedi.")

        scraped_data["posts"] = scraped_data["posts"][:5]
        scraped_data["post_times"] = scraped_data["post_times"][:5]
        scraped_data["images"] = scraped_data["images"][:3]
        return scraped_data


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] != "--stdin":
        print(json.dumps({"status": "failed", "error": "Usage: scraper.py --stdin"}))
        raise SystemExit(1)
    payload = json.load(sys.stdin)
    result = scrape_readonly(payload["target_url"], cookies=payload.get("cookies"))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
