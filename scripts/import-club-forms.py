#!/usr/bin/env python3
"""
從 Google 表單回覆產生當年度的社團 markdown 與圖片。

用法：
    python3 scripts/import-club-forms.py <表單回覆.csv> <"File responses" 目錄>

會做的事：
  * 依信箱裡的學號，把上傳的頭貼／背景／封面／內文圖片對回各社團
  * 把內文裡各種寫法的圖片引用（含填錯的檔名）換成 content 目錄的相對路徑
  * 超大圖縮到最長邊 4000px、HEIC/HEIF 轉成 JPEG，避免 sharp 在建置時失敗
  * 沒有回覆表單的社團，從前一年的集合沿用，並標記 dataYear

每年需要更新的是下方的 BOOTH_H / BOOTH_V（依當年度帳篷平面圖）與 CODE_FIX。
注意：本腳本用到 macOS 內建的 sips 處理圖片。
"""
import csv, difflib, hashlib, json, os, re, shutil, sys, unicodedata
from collections import defaultdict


MAX_EDGE = 4000
# 部署環境的 sharp 不見得帶 libheif，iPhone 直出的 HEIC/HEIF 一律先轉成 JPEG
CONVERT_EXT = {".heic": ".jpg", ".heif": ".jpg"}


def normalise_ext(ext):
    return CONVERT_EXT.get(ext.lower(), ext.lower())


def write_image(src, dst):
    """複製圖片到 content 目錄，必要時轉檔與縮圖。"""
    import subprocess

    src_ext = os.path.splitext(src)[1].lower()
    if src_ext in CONVERT_EXT:
        subprocess.run(["sips", "-s", "format", "jpeg", src, "--out", dst], capture_output=True)
    else:
        shutil.copyfile(src, dst)
    cap_dimensions(dst)


def cap_dimensions(path):
    """
    表單常收到手機全景或原始感光檔，最長邊動輒上萬像素。
    超過 16383px 時 sharp 無法輸出 WebP，建置會直接失敗；
    網站實際顯示也用不到那麼大，統一縮到最長邊 4000px。
    """
    import subprocess

    out = subprocess.run(
        ["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
        capture_output=True, text=True,
    ).stdout
    dims = [int(l.split(":")[1]) for l in out.splitlines() if ":" in l and l.split(":")[0].strip()
            in ("pixelWidth", "pixelHeight")]
    if dims and max(dims) > MAX_EDGE:
        subprocess.run(["sips", "-Z", str(MAX_EDGE), path], capture_output=True)


def dedupe_by_content(entries):
    """同一位上傳者重複送出表單時，同一張照片會出現多次，依內容雜湊去重。"""
    seen, out = set(), []
    for orig, ext, path in entries:
        h = hashlib.md5(open(path, "rb").read()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append((orig, ext, path))
    return out

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = sys.argv[1] if len(sys.argv) > 1 else ""
FILES = sys.argv[2] if len(sys.argv) > 2 else ""
OUT = os.path.join(ROOT, "src/content/clubs")
# 前一年的集合，用來沿用未回覆社團的資料，並保留 alternateNames 等人工維護的欄位
OLD = os.path.join(ROOT, "src/content/clubs2025")

FOLDERS = {
    "content": "內文圖片 (File responses)",
    "profileImage": "頭貼 (File responses)",
    "bgImage": "放在自己社團頁面的背景圖片 (File responses)",
    "cardImage": "放在自己社團頁面的封面圖片 (File responses)",
}

# 表單填錯代號的更正
CODE_FIX = {("B12", "講演社"): "A14"}

# ---------------------------------------------------------------- 115 平面圖
# 橫排攤位 1~39（右至左），club-x-22 為典禮臺
BOOTH_H = {
    1: ("A21", "軍武社"), 2: ("_A21", "軍武社"), 3: ("E09", "網球社"),
    4: ("A34", "模擬聯合國"), 5: ("A03", "物理研究社"), 6: ("A01", "科學研習社"),
    7: ("A06", "航空社"), 8: ("A07", "電子計算機研習社"), 9: ("CK2", "建中青年刊物社"),
    10: ("A08", "資訊社"), 11: ("C01", "信望愛社"), 12: ("A25", "英語辯論社"),
    13: ("A28", "物理辯論社"), 14: ("B12", "口技研究社"), 15: ("B13", "美食社"),
    16: ("CK3", "樂旗隊"), 17: ("B10", "攝影社"), 18: ("B20", "漫畫插畫研究社"),
    19: ("D04", "另類音樂創作社"), 20: ("A22", "小說創作研究社"), 21: ("B09", "美術社"),
    22: ("D10", "合唱團"), 23: ("D11", "嘻哈音樂研究社"), 24: ("B14", "魔術方塊社"),
    25: ("A20", "卡牌研究社"), 26: ("A13", "日本文化研究社"), 27: ("D08", "口琴社"),
    28: ("E04", "棒球社"), 29: ("A33", "Minecraft 邏輯研究社"), 30: ("B22", "西洋棋社"),
    31: ("D01", "爵士音樂社"), 32: ("B07", "圍棋社"), 33: ("D09", "國樂社"),
    34: ("B06", "象棋社"), 35: ("_SC0", "班聯會"), 36: ("A09", "國學暨人文社會學術研究社"),
    37: ("D05", "民謠吉他社"), 38: ("_TG0", "桌上遊戲社"), 39: ("A32", "建中機器人研究校隊暨社團"),
}
# 直排攤位 40~55（下至上）
BOOTH_V = {
    40: ("_MA0", "技擊社"), 41: ("B11", "大眾傳播社"), 42: ("D03", "流行音樂社"),
    43: ("A14", "講演社"), 44: ("A29", "建中創客社"), 45: ("D06", "古典吉他社"),
    46: ("A37", "人工智慧研究社"), 47: ("D07", "管弦樂社"), 48: ("A35", "世界地理探索社"),
    49: ("B17", "模型動畫社"), 50: ("A05", "天文社"), 51: ("A36", "韓國文化研究社"),
    52: ("C04", "聖經真理研究社"), 53: ("D02", "熱門音樂社"), 54: ("A02", "生物研究社"),
    55: ("C07", "駝鈴康輔社"),
}
EXPO_CODES = {c for c, _ in list(BOOTH_H.values()) + list(BOOTH_V.values())}

MEMBER_NORM = {"10 人以下": "10人以下(含)", "10人以下": "10人以下(含)"}


def norm_members(v):
    v = v.strip()
    return MEMBER_NORM.get(v, v)


def student_id(row):
    """從電子郵件或聯絡人姓名推出上傳者識別（檔名後綴用）。"""
    email = row[24].strip()
    if email:
        return email.split("@")[0]
    return None


def scan_uploads():
    """{folder_key: {student_id: [(original_basename, full_path)]}}"""
    out = {}
    for key, folder in FOLDERS.items():
        d = os.path.join(FILES, folder)
        by_id = defaultdict(list)
        by_name = defaultdict(list)
        for fn in sorted(os.listdir(d)):
            if fn.startswith("."):
                continue
            stem, ext = os.path.splitext(fn)
            if " - " not in stem:
                continue
            orig, uploader = stem.rsplit(" - ", 1)
            uploader = re.sub(r"\(\d+\)$", "", uploader).strip()
            m = re.match(r"(ck\d+)(.*)", uploader)
            sid, sname = (m.group(1), m.group(2)) if m else (uploader, uploader)
            entry = (orig, ext, os.path.join(d, fn))
            by_id[sid].append(entry)
            by_name[sname].append(entry)
        out[key] = (by_id, by_name)
    return out


def pick_uploads(uploads, key, sid, contact_name):
    by_id, by_name = uploads[key]
    if sid and sid in by_id:
        return by_id[sid]
    if contact_name and contact_name in by_name:
        return by_name[contact_name]
    return []


def parse_officers(raw):
    officers = []
    for line in raw.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        title = parts[0] if parts else ""
        name = parts[1] if len(parts) > 1 else ""
        contact = ",".join(parts[2:]).strip() if len(parts) > 2 else ""
        if not title and not name:
            continue
        if contact:
            m = re.search(r"instagram\.com/([^/?#\s]+)", contact)
            if m:
                contact = m.group(1)
            elif contact.startswith("http"):
                contact = contact  # 其他外部連結原樣保留
            contact = contact.lstrip("@")
        o = {"title": title, "name": name}
        if contact:
            o["contact"] = contact
        officers.append(o)
    return officers


PLATFORM_ALIAS = {
    "ig": "instagram", "instagram": "instagram", "insta": "instagram",
    "gmail": "gmail", "email": "gmail", "mail": "gmail", "信箱": "gmail",
    "yt": "youtube", "youtube": "youtube", "discord": "discord", "dc": "discord",
    "line": "line", "threads": "threads", "facebook": "facebook", "fb": "facebook",
    "linktree": "linktree", "website": "website", "網站": "website",
}


def parse_links(raw):
    links = []
    for line in raw.replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",", 1)]
        if len(parts) == 1:
            plat, val = ("website", parts[0])
        else:
            plat, val = parts
        key = PLATFORM_ALIAS.get(plat.strip().lower(), plat.strip().lower())
        val = val.strip()
        if not val:
            continue
        if val.startswith("mailto:"):
            key, handle, url = "gmail", val[7:], val
        elif "@" in val and not val.startswith("http"):
            key, handle, url = "gmail", val, "mailto:" + val
        elif val.startswith("http"):
            url = val
            m = re.search(r"instagram\.com/([^/?#\s]+)", url)
            if m:
                key, handle = "instagram", m.group(1)
            else:
                handle = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
        else:
            handle = val.lstrip("@")
            if key == "instagram":
                url = "https://www.instagram.com/" + handle
            elif key == "threads":
                url = "https://www.threads.net/@" + handle
            elif key == "youtube":
                url = "https://www.youtube.com/@" + handle
            elif key == "discord":
                url = "https://discord.gg/" + handle
            else:
                url = handle if handle.startswith("http") else "https://" + handle
        links.append({"platform": key, "handle": handle, "url": url})
    return links


def parse_activities(raw):
    parts = re.split(r"[、,，/\n]+", raw)
    return [p.strip() for p in parts if p.strip() and p.strip() != "無"]


def parse_tags(a, b):
    tags, seen = [], set()
    for chunk in (a, b):
        for t in re.split(r"[,，]", chunk):
            t = t.strip()
            if t and t not in seen and t not in ("是", "否"):
                seen.add(t)
                tags.append(t)
    return tags


IMG_EXT = r"jpe?g|png|webp|gif|hei[cf]|avif|bmp|tiff?"

# 表單填的圖片語法五花八門，這裡一次涵蓋：
#   ![說明](檔名)  ![說明]（檔名）  ![說明]檔名   [說明](檔名)   說明(檔名)   ![檔名]
IMG_RE = re.compile(
    rf"!?\[([^\]]*)\]\s*[(（]\s*([^)）]+?)\s*[)）]"
    rf"|!\[([^\]]*)\]\s*([^\s()（）\[\]]+\.(?:{IMG_EXT}))"
    rf"|([^\s()（）\[\]!]*)[(（]\s*([^)）]*?\.(?:{IMG_EXT}))\s*[)）]"
    rf"|!?\[\s*([^\]\s][^\]]*\.(?:{IMG_EXT}))\s*\](?!\s*[(（])",
    re.IGNORECASE,
)


def match_parts(m):
    """把 IMG_RE 的各組分支還原成 (說明, 目標檔名)。"""
    for alt_i, ref_i in ((1, 2), (3, 4), (5, 6)):
        if m.group(ref_i) is not None:
            return m.group(alt_i) or "", m.group(ref_i).strip()
    # 只把檔名塞在中括號裡、沒寫目標的寫法，說明就用去掉副檔名的檔名
    if m.group(7) is not None:
        ref = m.group(7).strip()
        return os.path.splitext(os.path.basename(ref))[0], ref
    return "", ""


def looks_like_image(ref):
    """外部連結與一般文字不動，只有看起來是圖檔名稱的才會被換成圖片。"""
    if not ref or re.match(r"^(https?:|mailto:|/|#)", ref, re.I):
        return False
    return re.search(rf"\.(?:{IMG_EXT})$", ref, re.I) is not None


def img_key(stem):
    """把檔名正規化：去掉相機／手機自動加上的 ~N 副本標記與大小寫差異。"""
    return re.sub(r"~\d+$", "", stem).strip().lower()


def normalise_body(text):
    """修正表單常見的 markdown 瑕疵。"""
    lines = []
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        # Discord 風格的小字語法 -# xxx
        if s.startswith("-#"):
            s = s[2:].strip()
            line = s
        # 全形井號當標題用：＃標題 -> # 標題
        line = re.sub(r"^＃+", lambda mm: "#" * len(mm.group(0)), line)
        # 標題缺空格：#標題 -> # 標題
        line = re.sub(r"^(#{1,6})(?=[^\s#])", r"\1 ", line)
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def build_body(raw, stem, content_files):
    """把內文中的原始檔名換成 content-N 路徑，並回傳需要複製的檔案清單。"""
    by_orig = {}
    for entry in content_files:
        orig, ext, path = entry
        by_orig.setdefault(img_key(orig), []).append(entry)
        by_orig.setdefault(img_key(orig + ext), []).append(entry)

    body_src = normalise_body(raw)
    # 依出現順序記錄 (說明, 原始檔名)；不是圖片的比對結果記成 None，之後原樣保留
    refs = []
    for m in IMG_RE.finditer(body_src):
        alt, ref = match_parts(m)
        refs.append((alt, os.path.basename(ref)) if looks_like_image(ref) else None)

    # 第一輪只認完全相符的檔名，避免模糊比對搶走別人的圖
    resolved = [None] * len(refs)
    used = set()
    for i, r in enumerate(refs):
        if r is None:
            continue
        base = r[1]
        cand = by_orig.get(img_key(base)) or by_orig.get(img_key(os.path.splitext(base)[0]))
        cand = [c for c in (cand or []) if c[2] not in used]
        if cand:
            resolved[i] = cand[0]
            used.add(cand[0][2])

    # 第二輪：表單填的檔名常有筆誤或多餘描述，對剩下的圖做模糊比對
    unresolved = []
    for i, r in enumerate(refs):
        if r is None or resolved[i]:
            continue
        base = r[1]
        key = img_key(os.path.splitext(base)[0])
        free = [c for c in content_files if c[2] not in used]
        cand = ([c for c in free if key in img_key(c[0]) or img_key(c[0]) in key]
                or [c for c in free
                    if difflib.get_close_matches(key, [img_key(c[0])], 1, 0.85)])
        if not cand:
            unresolved.append(base)
            cand = free
        if cand:
            resolved[i] = cand[0]
            used.add(cand[0][2])

    assigned = {}      # path -> index
    copies = []        # (index, ext, src)

    def take(path, ext):
        if path not in assigned:
            assigned[path] = len(copies)
            copies.append((len(copies), ext, path))
        return assigned[path]

    it = iter(range(len(refs)))

    def repl(m):
        i = next(it)
        if refs[i] is None:
            return m.group(0)  # 一般連結或純文字，原樣保留
        alt = refs[i][0]
        entry = resolved[i]
        if entry is None:
            return ""  # 沒有圖可用，移除該引用
        _, ext, path = entry
        idx = take(path, ext)
        return f"![{alt}](./images/{stem}/{stem}-content-{idx}{normalise_ext(ext)})"

    body = IMG_RE.sub(repl, body_src)

    # 未被引用到的圖片附在文末
    extras = [c for c in content_files if c[2] not in used]
    if extras:
        tail = []
        for orig, ext, path in extras:
            idx = take(path, ext)
            tail.append(f"![社團照片](./images/{stem}/{stem}-content-{idx}{normalise_ext(ext)})")
        body = body.rstrip() + "\n\n" + "\n\n".join(tail)

    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body, copies, unresolved


def q(s):
    return json.dumps(s, ensure_ascii=False)


def read_old(path):
    txt = open(path, encoding="utf-8").read()
    fm = txt.split("---", 2)[1]
    return txt, fm


def old_field_block(fm, key):
    m = re.search(rf"^{key}:\n((?:\s*-\s+.*\n)+)", fm, re.M)
    if not m:
        return None
    return [l.strip()[2:].strip() for l in m.group(1).strip().split("\n")]


def old_scalar(fm, key):
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip() if m else None


def main():
    if not CSV or not FILES:
        sys.exit(__doc__)

    rows = list(csv.reader(open(CSV, encoding="utf-8")))[1:]
    uploads = scan_uploads()

    # 舊資料索引：clubCode -> (stem, frontmatter)
    old_by_code = {}
    for fn in sorted(os.listdir(OLD)):
        if not fn.endswith(".md"):
            continue
        stem = fn[:-3]
        _, fm = read_old(os.path.join(OLD, fn))
        old_by_code[stem.split("-")[0]] = (stem, fm)

    # 去重：同一 clubCode 取最後一筆（時間較新）
    latest = {}
    for row in rows:
        code = row[4].strip().upper()
        name = row[1].strip()
        code = CODE_FIX.get((code, name), code)
        latest[code] = row

    report = {"generated": [], "carried": [], "no_data": [], "warnings": []}

    for code, row in sorted(latest.items()):
        name = row[1].strip()
        sid = student_id(row)
        contact_name = row[2].strip()
        old = old_by_code.get(code)
        stem = old[0] if old else f"{code}-{name}"
        img_dir = os.path.join(OUT, "images", stem)
        os.makedirs(img_dir, exist_ok=True)

        # --- 圖片 ---
        imgs = {}
        for key in ("profileImage", "bgImage", "cardImage"):
            got = pick_uploads(uploads, key, sid, contact_name)
            if got:
                orig, ext, src = got[0]
                dst = os.path.join(img_dir, f"{stem}-{key}{normalise_ext(ext)}")
                write_image(src, dst)
                imgs[key] = f"./images/{stem}/{os.path.basename(dst)}"
        if "cardImage" not in imgs and "bgImage" in imgs:
            src = os.path.join(OUT, imgs["bgImage"].replace("./", ""))
            ext = os.path.splitext(src)[1]
            dst = os.path.join(img_dir, f"{stem}-cardImage{ext}")
            shutil.copyfile(src, dst)  # 已經處理過，直接複製
            imgs["cardImage"] = f"./images/{stem}/{os.path.basename(dst)}"
            report["warnings"].append(f"{code} {name}：缺封面圖，改用背景圖")
        missing = [k for k in ("profileImage", "bgImage", "cardImage") if k not in imgs]
        if missing:
            report["warnings"].append(f"{code} {name}：缺少 {', '.join(missing)}")
            continue

        content_files = dedupe_by_content(pick_uploads(uploads, "content", sid, contact_name))
        body, copies, unresolved = build_body(row[18], stem, content_files)
        if unresolved:
            report["warnings"].append(f"{code} {name}：內文引用的圖片找不到對應檔案 {unresolved}")
        for idx, ext, src in copies:
            write_image(src, os.path.join(img_dir, f"{stem}-content-{idx}{normalise_ext(ext)}"))

        # --- frontmatter ---
        ts = row[0].strip()
        m = re.match(r"(\d+)/(\d+)/(\d+) (上午|下午) (\d+):(\d+):(\d+)", ts)
        if m:
            y, mo, d, ap, h, mi, s = m.groups()
            h = int(h) % 12 + (12 if ap == "下午" else 0)
            timestamp = f"{y}-{int(mo):02d}-{int(d):02d}T{h:02d}:{mi}:{s}"
        else:
            timestamp = "2026-07-01T00:00:00"

        alt = old_field_block(old[1], "alternateNames") if old else None
        has_stamp = (old_scalar(old[1], "hasClubStamp") == "true") if old else False
        map_id = old_scalar(old[1], "mapId") if old else None

        lines = [
            "---",
            f"timestamp: {timestamp}",
            f"dataYear: 2026",
            "",
            f"name: {q(name)}",
        ]
        if alt:
            lines.append("alternateNames:")
            lines += [f"  - {q(a)}" for a in alt]
        lines += [
            "",
            f"clubCode: {q(code)}",
            f"attendsExpo: {'true' if code in EXPO_CODES else 'false'}",
            f"hasClubStamp: {'true' if has_stamp else 'false'}",
            f"acceptsUnofficial: {'true' if row[13].strip() == '是' else 'false'}",
            "",
            f"summary: {q(re.sub(r'\\s+', ' ', row[17]).strip())}",
            "",
            "members:",
            f"  current: {q(norm_members(row[8]))}",
            f"  previousYear: {q(norm_members(row[9]))}",
            "",
            f"membershipFee: {q(row[10].strip())}",
            "",
            "workshops:",
            f"  has: {'true' if row[14].strip() == '是' else 'false'}",
            f"  description: {q(row[15].strip())}",
            "",
        ]
        acts = parse_activities(row[16])
        if acts:
            lines.append("activities:")
            lines += [f"  - {q(a)}" for a in acts]
        else:
            lines.append("activities: []")
        lines.append("")

        tags = parse_tags(row[11], row[12])
        lines.append("tags:" if tags else "tags: []")
        lines += [f"  - {q(t)}" for t in tags]
        lines.append("")

        officers = parse_officers(row[6])
        lines.append("officers:" if officers else "officers: []")
        for o in officers:
            lines.append(f"  - title: {q(o['title'])}")
            lines.append(f"    name: {q(o['name'])}")
            if o.get("contact"):
                lines.append(f"    contact: {q(o['contact'])}")
        lines.append("")

        links = parse_links(row[7])
        lines.append("links:" if links else "links: []")
        for l in links:
            lines.append(f"  - platform: {q(l['platform'])}")
            lines.append(f"    handle: {q(l['handle'])}")
            lines.append(f"    url: {q(l['url'])}")
        lines.append("")

        for key in ("profileImage", "bgImage", "cardImage"):
            lines.append(f"{key}: {imgs[key]}")
        if map_id:
            lines.append("")
            lines.append(f"mapId: {q(map_id)}")
        lines += ["---", "", body, ""]

        open(os.path.join(OUT, stem + ".md"), "w", encoding="utf-8").write("\n".join(lines))
        report["generated"].append(f"{code} {name} -> {stem}.md ({len(copies)} 張內文圖)")

    # --- 沿用去年資料的社團 ---
    for code, (stem, fm) in sorted(old_by_code.items()):
        if code in latest:
            continue
        src_md = os.path.join(OLD, stem + ".md")
        txt = open(src_md, encoding="utf-8").read()
        txt = txt.replace("---\ntimestamp:", "---\ndataYear: 2025\ntimestamp:", 1)
        txt = re.sub(r"^attendsExpo:\s*\S+$",
                     f"attendsExpo: {'true' if code in EXPO_CODES else 'false'}", txt, count=1, flags=re.M)
        open(os.path.join(OUT, stem + ".md"), "w", encoding="utf-8").write(txt)
        shutil.copytree(os.path.join(OLD, "images", stem),
                        os.path.join(OUT, "images", stem), dirs_exist_ok=True)
        report["carried"].append(f"{code} {stem}")

    for code, name in sorted(set(list(BOOTH_H.values()) + list(BOOTH_V.values()))):
        if code.startswith("_"):
            continue
        if code not in latest and code not in old_by_code:
            report["no_data"].append(f"{code} {name}")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
