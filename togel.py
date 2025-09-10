import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

# upload target
UPLOAD_URL = "https://prediksi.gbg-coc.org/upload.php"

# === Playwright helpers ===
def get_prediksi_links(page, url):
    page.goto(url, wait_until="load", timeout=60000)
    page.wait_for_timeout(5000)
    locator = page.locator("a.btn.btn-sm.btn-warning:has-text('Lihat Prediksi')")
    try:
        count = locator.count()
    except Exception:
        count = 0
    links = []
    for i in range(count):
        try:
            link = locator.nth(i).get_attribute("href")
        except Exception:
            link = None
        if link:
            links.append(link)
    return links

def get_rendered_html(page, url):
    page.goto(url, wait_until="load", timeout=60000)
    page.wait_for_timeout(5000)
    # optional: remove scripts to reduce noise (comment/uncomment if perlu)
    try:
        page.evaluate("() => { document.querySelectorAll('script').forEach(n => n.remove()); }")
    except Exception:
        pass
    return page.content()

# =========================
# Bersihkan / modifikasi HTML (ikut semua aturanmu)
# =========================
def clean_html(html_raw):
    # perbaikan path & beberapa replace awal
    html = re.sub(r'src=["\']js/', 'src="https://olx29.ramalan.info/js/', html_raw)
    html = re.sub(r'href=["\']css/', 'href="https://olx29.ramalan.info/css/', html)
    html = re.sub(r'src=["\']images/', 'src="https://olx29.ramalan.info/images/', html)
    html = re.sub(r'href=["\']images/', 'href="https://olx29.ramalan.info/images/', html)
    html = re.sub(r'href=["\']\?page=', 'href="https://prediksi.gbg-coc.org/?page=', html)
    html = re.sub(r'<form[\s\S]*?<select[^>]*id=["\']selectprediksi["\'][\s\S]*?</form>', '', html, flags=re.IGNORECASE)
    html = re.sub(r' Dari Bandar OLXTOTO', '', html)
    html = re.sub(r'OLXTOTO', '', html)
    html = re.sub(r'<h6 class="title-wa m-0"><i class="fab fa-whatsapp"></i> Whatsapp</h6>', '', html)
    html = re.sub(r' sebelumnya:', '', html)

    # hapus carousel sampai <!-- /Mainbar -->
    html = re.sub(
        r'<div\s+class=["\']owl-carousel prediksi-sebelum my-3 owl-theme owl-loaded owl-drag["\'][\s\S]*?<!--\s*/Mainbar\s*-->',
        '',
        html,
        flags=re.IGNORECASE
    )

    # ubah blok Live draw ... Panduan jadi single Prediksi Togel link
    html = re.sub(
        r'<a[^>]*href=["\']https://prediksi\.gbg-coc\.org/\?page=livedraw-togel["\'][^>]*>Live draw</a>.*?<a[^>]*href=["\']https://surkale\.me/ZcYzfO[^"\']*["\'][^>]*>Panduan</a>',
        '<a class="nav-link active" href="https://prediksi.gbg-coc.org/?page=prediksi-togel">Prediksi Togel</a>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    # ubah link Home (opsional sesuai skripmu)
    html = re.sub(
        r'<a[^>]*href="/"\s*[^>]*>\s*<i class="fas fa-home"></i>\s*Home\s*</a>',
        '<a aria-current="page" class="nav-link" href="https://hasil.gbg-coc.org/"><i class="fas fa-home"></i> Home</a>',
        html,
        flags=re.IGNORECASE
    )

    # blok-besar yang dihapus (ikut aturanmu)
    pattern_block = (
        r'<h1\s*>\s*<strong[^>]*>[\s\S]*?–\s*Situs\s*Bandar\s*Prediksi\s*Togel\s*Terjitu[\s\S]*?'
        r'dengan\s+sangat\s+mudah\s+di\s+Olxtoto\s+slot\s+gacor\.\s*</p>\s*</div>'
    )
    html = re.sub(pattern_block, '', html, flags=re.IGNORECASE)

    # ganti gambar spesifik
    html = html.replace(
        "https://photoku.io/images/2025/08/13/Fjf6rkzW.png",
        "https://i.postimg.cc/HWSJVRvt/image.png"
    )
    html = html.replace(
        "https://olx29.ramalan.info/images/icon-apk.webp",
        "https://i.postimg.cc/CKXg3Cck/image-removebg-preview-1.png"
    )

    replacements = {
        "https://photoku.io/images/2025/08/13/bg-olx-baruu1.webp":
            "https://aix-asset.s3.ap-southeast-1.amazonaws.com/global/seamless/1626/IDR/background/331017492.png",
        "https://imgstore.io/images/2025/02/15/icon.png":
            "https://i.postimg.cc/CKXg3Cck/image-removebg-preview-1.png",
    }
    for old, new in replacements.items():
        html = html.replace(old, new)

    # hapus blok judul panjang (RESULT / OLXTOTO)
    pattern_result_block = (
        r'<h1\s*>\s*<strong[^>]*>\s*RESULT\s+TOGEL[\s\S]*?'
        r'dengan\s+sangat\s+mudah\s+di\s+Olxtoto\s+slot\s+gacor\.\s*</p>\s*</div>'
    )
    html = re.sub(pattern_result_block, '', html, flags=re.IGNORECASE)

    pattern_olx_block = (
        r'<h1\s*>\s*<strong[^>]*>\s*OLXTOTO[\s\S]*?'
        r'dengan\s+sangat\s+mudah\s+di\s+Olxtoto\s+slot\s+gacor\.\s*</p>\s*</div>'
    )
    html = re.sub(pattern_olx_block, '', html, flags=re.IGNORECASE)

    # parse pakai BeautifulSoup lalu decompose elemen tertentu
    soup = BeautifulSoup(html, "html.parser")

    for mobile_div in soup.select("div.d-lg-none.d-sm-block"):
        mobile_div.decompose()
    for footer in soup.select("footer.text-center.text-light.py-3"):
        footer.decompose()
    for pagination in soup.select("div.swiper-pagination.swiper-pagination-progressbar.swiper-pagination-horizontal"):
        pagination.decompose()
    for slide in soup.select("div.swiper-slide"):
        slide.decompose()
    for slider in soup.select("div.swiper.slider-blog.swiper-initialized.swiper-horizontal.swiper-backface-hidden"):
        slider.decompose()
    for banner_div in soup.select("div.col-lg-5.d-none.d-lg-block"):
        banner_div.decompose()

    for btn in soup.select("a.btn.btn-sm.btn-warning, a.btn.btn-sm.btn-danger"):
        if any(text in btn.text for text in ["RTP Slot", "Promo", "Login"]):
            btn.decompose()

    for div in soup.select("div.col-md.col-6.d-grid"):
        button = div.find("button", class_="btntabb")
        if button and "Result Togel" not in button.text:
            div.decompose()

    for span in soup.select("span.position-absolute.notify.translate-middle.badge.rounded-pill.bg-primary"):
        parent_button = span.find_parent("div", class_="col-md col-6 d-grid")
        if parent_button and parent_button.find("button") and "Result Togel" not in parent_button.find("button").text:
            span.decompose()

    for winner in soup.select("div.winner-wrapper"):
        winner.decompose()
    for top_nav in soup.select("div.top-nav"):
        top_nav.decompose()
    for wa_link in soup.select('a[href="https://api.whatsapp.com/send?phone=6282160303218"]'):
        wa_link.decompose()

    # replace teks tertentu
    for tag in soup.find_all(string=True):
        if "SELAMAT DATANG DI OLXTOTO BANDAR TOGEL" in tag:
            tag.replace_with(tag.replace("SELAMAT DATANG DI OLXTOTO BANDAR TOGEL", "SELAMAT DATANG DI RESULT TOGEL HARI INI"))
        if "OLXTOTO – Situs Bandar Prediksi Togel Terjitu" in tag:
            tag.replace_with(tag.replace("OLXTOTO – Situs Bandar Prediksi Togel Terjitu", "RESULT TOGEL – Situs Bandar Prediksi Togel Terjitu"))
        if "OLXTOTO situs bandar togel dengan prediksi terbaik" in tag:
            tag.replace_with(tag.replace("OLXTOTO situs bandar togel dengan prediksi terbaik", "RESULT TOGEL situs bandar togel dengan prediksi terbaik"))

    # --- Hapus page terakhir otomatis (angka tertinggi) ---
    page_links = soup.find_all("a", class_="page-link")
    if page_links:
        try:
            max_no = 0
            last_link = None
            for link in page_links:
                try:
                    no = int(link.text.strip())
                    if no > max_no:
                        max_no = no
                        last_link = link
                except ValueError:
                    continue
            if last_link:
                last_link.decompose()
        except Exception as e:
            print(f"⚠️ Gagal hapus page terakhir: {e}")

    return str(soup)

# =========================
# Modifikasi tombol Prediksi Togel (sesuai skripmu)
# =========================
def process_html(html: str) -> str:
    cleaned_html = clean_html(html)
    soup = BeautifulSoup(cleaned_html, "html.parser")

    for btn in soup.find_all("button", class_="btntabb"):
        if "Prediksi Togel" in btn.text:
            btn.attrs.pop("onclick", None)
            new_html = f'<a href="./">{str(btn)}</a>'
            btn.replace_with(BeautifulSoup(new_html, "html.parser"))

    return str(soup)

# =========================
# Ambil parameter dari link asli
# =========================
def extract_params(src_url: str):
    parsed = urlparse(src_url)
    query = parse_qs(parsed.query)
    page = query.get("page", ["prediksi-togel"])[0]
    pasaran = query.get("pasaran", ["unknown"])[0]
    tanggal = query.get("tanggal", ["unknown"])[0]
    return page, pasaran, tanggal

# =========================
# Upload ke server
# =========================
def upload_to_server(html: str, page: str, pasaran: str, tanggal: str):
    files = {"file": ("index.html", html, "text/html")}
    data = {"page": page, "pasaran": pasaran, "tanggal": tanggal}
    try:
        r = requests.post(UPLOAD_URL, files=files, data=data, timeout=30)
        print(f"[UPLOAD] ?page={page}&pasaran={pasaran}&tanggal={tanggal} → {r.status_code}")
        print("Server:", r.text)
    except Exception as e:
        print(f"[ERROR] Upload {page}/{pasaran}/{tanggal} → {e}")

# =========================
# MAIN: Ambil link, ambil html tiap link, bersihkan, upload (tanpa simpan file)
# =========================
if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page_no = 1
        while page_no <= 10:
            if page_no == 1:
                main_url = "https://olx29.ramalan.info/?page=prediksi-togel"
            else:
                main_url = f"https://olx29.ramalan.info/?page=prediksi-togel&no={page_no}"

            print(f"🔎 Ambil link dari: {main_url}")
            try:
                links = get_prediksi_links(page, main_url)
            except Exception as e:
                print(f"❌ Gagal ambil daftar link di {main_url}: {e}")
                break

            if not links:
                print(f"❌ Tidak ada link lagi di halaman {page_no}, stop.")
                break

            for idx, link in enumerate(links, start=1):
                if not link.startswith("http"):
                    link = "https://olx29.ramalan.info/" + link.lstrip("/")
                print(f"➡️ Ambil HTML dari {link}")

                try:
                    raw_html = get_rendered_html(page, link)
                except Exception as e:
                    print(f"❌ Gagal ambil HTML {link}: {e}")
                    continue

                try:
                    mod_html = process_html(raw_html)
                except Exception as e:
                    print(f"❌ Gagal proses HTML {link}: {e}")
                    continue

                page_param, pasaran, tanggal = extract_params(link)
                upload_to_server(mod_html, page_param, pasaran, tanggal)

            page_no += 1

        browser.close()
