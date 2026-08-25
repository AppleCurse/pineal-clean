"""X (Twitter) kaziyici — B4: DEVRE DISI (durust kapatma).

Bu dosya eskiden `browser_oxide` adli bir pakete dayanan X (Twitter)
kazima yoluydu. Adli denetim su sorunlari kanitladi:
  1) browser_oxide requirements.txt'te yoktu ve PyPI'da bulunmuyor
     (pip: "No matching distribution found"),
  2) basari yolunda return ifadesi eksikti,
  3) runtime'da tarayici binary'si yokken yol zaten kiriliyordu.

B4 KARARI: X kazima yeniden yazilMADI; yol acikca "desteklenmiyor"
durumuna getirildi. Bu fonksiyon hicbir veri UYDURMAZ ve sessizce bos
sonuc DONMEZ; cagiran taraf desteklenmedigini acikca gorur.
Instagram kazima yolu (agent_core/scraper/instagram_ghost.py) aktiftir.

NOT (ayri kapsam): /api/telemetry'deki 'scraper:true' degeri yalnizca
import basarisini olcer; gercek yetenek raporu wiring kapisinda.
"""

import json
import sys
from typing import NoReturn


class XScraperUnsupportedError(RuntimeError):
    """X (Twitter) kazimasi desteklenmiyor (B4 ile devre disi birakildi)."""


def scrape_readonly(profile_url: str, cookies: str = None) -> NoReturn:
    """X (Twitter) kazimasi desteklenmiyor.

    B4: browser_oxide kaldirildi; Playwright tabanli yeniden yazim ayri
    bir is paketi olarak kayitlidir. Bu yol veri uydurmaz ve sessizce
    bos sonuc donmez; cagiran taraf desteklenmedigini acikca gorur.
    """
    raise XScraperUnsupportedError(
        "X (Twitter) kazimasi desteklenmiyor (B4: browser_oxide kaldirildi). "
        "Instagram kazima yolunu kullanin: agent_core/scraper/instagram_ghost.py"
    )


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] != "--stdin":
        print(json.dumps({"status": "failed", "error": "Usage: scraper.py --stdin"}))
        raise SystemExit(1)
    payload = json.load(sys.stdin)
    try:
        scrape_readonly(payload["target_url"], cookies=payload.get("cookies"))
    except XScraperUnsupportedError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
