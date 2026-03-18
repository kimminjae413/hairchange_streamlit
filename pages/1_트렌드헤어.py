"""
트렌드 헤어 갤러리
Google Trends + Google Custom Search + Gemini Vision 기반 실시간 헤어스타일 트렌드
"""
import streamlit as st
import requests
import json
import os
import io
import time
from datetime import datetime
from PIL import Image

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="트렌드 헤어 갤러리",
    page_icon="💇",
    layout="wide",
)

# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------

def _get_key(name: str):
    """Read key from os.environ, st.secrets, or .env file."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    # Try .env in project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{name}="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return None


GOOGLE_API_KEY = _get_key("GOOGLE_API_KEY")
GOOGLE_CX = _get_key("GOOGLE_CX")
GEMINI_API_KEY = _get_key("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Constants — categories and fallback keywords
# ---------------------------------------------------------------------------

CATEGORIES = {
    "20대 여성": {
        "pytrends_kw": ["20대 여자 헤어스타일", "여자 헤어 트렌드"],
        "fallback": [
            "2025 20대 여자 헤어스타일 트렌드",
            "허쉬컷 레이어드",
            "20대 여성 염색",
        ],
    },
    "30대 여성": {
        "pytrends_kw": ["30대 여자 헤어", "여성 단발 펌"],
        "fallback": [
            "30대 여자 단발 펌 트렌드",
            "30대 직장인 헤어",
            "30대 여성 C컬",
        ],
    },
    "40대 여성": {
        "pytrends_kw": ["40대 여자 헤어", "40대 볼륨펌"],
        "fallback": [
            "40대 여자 볼륨펌",
            "40대 젊어보이는 헤어",
            "40대 여성 단발",
        ],
    },
    "50대 여성": {
        "pytrends_kw": ["50대 여자 헤어", "중년 여성 헤어"],
        "fallback": [
            "50대 여자 헤어스타일",
            "50대 숏컷 펌",
            "중년여성 젊어보이는 머리",
        ],
    },
    "60대+ 여성": {
        "pytrends_kw": ["60대 여자 헤어", "시니어 헤어"],
        "fallback": [
            "60대 시니어 헤어",
            "60대 숏컷",
            "어르신 헤어스타일",
        ],
    },
    "20대 남성": {
        "pytrends_kw": ["남자 헤어스타일 트렌드", "남자 투블럭"],
        "fallback": [
            "남자 헤어스타일 트렌드 2025",
            "남자 투블럭",
            "남자 댄디컷",
        ],
    },
    "30대 남성": {
        "pytrends_kw": ["30대 남자 헤어", "남자 가르마펌"],
        "fallback": [
            "30대 남자 헤어",
            "남자 가르마펌",
            "직장인 남자 헤어",
        ],
    },
    "40대+ 남성": {
        "pytrends_kw": ["40대 남자 헤어", "중년 남성 헤어"],
        "fallback": [
            "40대 남자 헤어",
            "중년 남성 숏컷",
            "남자 볼륨펌",
        ],
    },
}

FAVORITES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "trend_favorites.json"
)

# ---------------------------------------------------------------------------
# Favorites persistence
# ---------------------------------------------------------------------------

def _load_favorites():
    try:
        if os.path.exists(FAVORITES_PATH):
            with open(FAVORITES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_favorites(favs):
    os.makedirs(os.path.dirname(FAVORITES_PATH), exist_ok=True)
    with open(FAVORITES_PATH, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


def add_favorite(item):
    fav = {
        "url": item.get("url", ""),
        "title": item.get("title", ""),
        "style_name": item.get("style_name", item.get("title", "")),
        "trend_score": item.get("trend_score", 0),
        "category": item.get("category", ""),
        "added_at": datetime.now().isoformat(),
    }
    if not any(f["url"] == fav["url"] for f in st.session_state.favorites):
        st.session_state.favorites.append(fav)
        _save_favorites(st.session_state.favorites)
        return True
    return False


def remove_favorite(url):
    st.session_state.favorites = [f for f in st.session_state.favorites if f["url"] != url]
    _save_favorites(st.session_state.favorites)


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "trend_results" not in st.session_state:
    st.session_state.trend_results = []
if "trend_keywords" not in st.session_state:
    st.session_state.trend_keywords = []
if "favorites" not in st.session_state:
    st.session_state.favorites = _load_favorites()
if "selected_reference" not in st.session_state:
    st.session_state.selected_reference = None
if "show_favorites" not in st.session_state:
    st.session_state.show_favorites = False

# ---------------------------------------------------------------------------
# 1. Trending keywords via pytrends (with fallback)
# ---------------------------------------------------------------------------

def get_trending_keywords(category):
    """Try pytrends first, fall back to predefined list."""
    cat = CATEGORIES.get(category)
    if not cat:
        return []

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540, timeout=(5, 10))
        all_kw = []
        for kw in cat["pytrends_kw"]:
            try:
                pytrends.build_payload([kw], timeframe="today 3-m", geo="KR")
                related = pytrends.related_queries()
                if kw in related:
                    rising = related[kw].get("rising")
                    if rising is not None and not rising.empty:
                        all_kw.extend(rising["query"].tolist()[:5])
                    top = related[kw].get("top")
                    if top is not None and not top.empty:
                        all_kw.extend(top["query"].tolist()[:3])
            except Exception:
                continue

        # Deduplicate preserving order
        seen = set()
        unique = []
        for k in all_kw:
            kl = k.strip().lower()
            if kl not in seen:
                seen.add(kl)
                unique.append(k.strip())
        if unique:
            return unique[:10]
    except ImportError:
        pass
    except Exception:
        pass

    return cat["fallback"]


# ---------------------------------------------------------------------------
# 2. Image search — Google Custom Search or DuckDuckGo fallback
# ---------------------------------------------------------------------------

def search_images_google(query, num=10):
    """Google Custom Search JSON API — image search."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return []
    results = []
    for start in range(1, num + 1, 10):
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": GOOGLE_API_KEY,
                    "cx": GOOGLE_CX,
                    "q": query,
                    "searchType": "image",
                    "num": min(10, num - start + 1),
                    "start": start,
                    "imgSize": "LARGE",
                    "safe": "active",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    results.append({
                        "url": item.get("link", ""),
                        "title": item.get("title", ""),
                        "source": item.get("displayLink", ""),
                        "snippet": item.get("snippet", ""),
                        "thumbnail": item.get("image", {}).get("thumbnailLink", ""),
                    })
        except Exception:
            pass
    return results


def search_images_ddg(query, num=10):
    """DuckDuckGo image search fallback."""
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.images(query, region="kr-kr", safesearch="moderate", max_results=num))
        return [
            {
                "url": r.get("image", ""),
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "snippet": r.get("title", ""),
                "thumbnail": r.get("thumbnail", ""),
            }
            for r in raw
        ]
    except Exception:
        return []


def search_images(query, num=10):
    """Try Google Custom Search first, then DDG fallback."""
    results = search_images_google(query, num)
    if not results:
        results = search_images_ddg(query, num)
    return results


# ---------------------------------------------------------------------------
# 3. Image download (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def download_image_bytes(url):
    """Download image and return raw bytes. Returns None on failure."""
    try:
        resp = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            # Validate it's actually an image
            img = Image.open(io.BytesIO(resp.content))
            img.verify()
            return resp.content
    except Exception:
        pass
    return None


def bytes_to_pil(raw_bytes):
    """Convert raw bytes to RGB PIL Image."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 4. Gemini Vision analysis
# ---------------------------------------------------------------------------

def analyze_images_with_gemini(images):
    """
    Analyze images with Gemini Vision in batches.
    Augments each image dict with style_name, trend_score, description, etc.
    """
    if not GEMINI_API_KEY:
        _fill_defaults(images)
        return images

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        _fill_defaults(images)
        return images

    from google.genai import types

    batch_size = 5
    for i in range(0, len(images), batch_size):
        batch = images[i : i + batch_size]
        parts = []
        valid_indices = []

        for j, img in enumerate(batch):
            raw = download_image_bytes(img["url"])
            if raw:
                try:
                    pil = bytes_to_pil(raw)
                    if pil is None:
                        continue
                    buf = io.BytesIO()
                    pil.save(buf, format="JPEG", quality=80)
                    parts.append(
                        types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
                    )
                    parts.append(
                        types.Part.from_text(text=f"[이미지 {j}] 제목: {img.get('title', '')}")
                    )
                    valid_indices.append(j)
                except Exception:
                    pass

        if not valid_indices:
            _fill_defaults(batch)
            continue

        prompt = f"""당신은 헤어스타일 트렌드 전문가입니다. 아래 {len(valid_indices)}개 헤어스타일 이미지를 분석해주세요.

각 이미지에 대해 아래 JSON 형식으로만 답변해주세요 (다른 텍스트 없이):
{{
  "images": [
    {{
      "index": 0,
      "style_name": "스타일 한국어 이름 (예: 레이어드 보브컷)",
      "trend_score": 8,
      "is_clean_photo": true,
      "description": "한 줄 설명",
      "suitable_age": "적합 연령대",
      "keywords": ["키워드1", "키워드2"]
    }}
  ]
}}

- index는 이미지 번호 [이미지 0], [이미지 1] ... 순서대로
- trend_score는 1-10 (현재 2025 트렌드 반영도)
- is_clean_photo: 아래 경우 false로 설정:
  * 이미지에 텍스트/글자/자막이 있는 경우 (블로그 썸네일, 유튜브 캡처 등)
  * 여러 사진이 콜라주/합성된 경우
  * 워터마크가 크게 있는 경우
  * 헤어스타일이 아닌 이미지
  * 해상도가 낮거나 흐린 이미지
  순수한 헤어스타일 사진만 true로 설정해주세요
- 헤어스타일이 아닌 이미지는 trend_score를 1로 주세요
"""
        parts.append(types.Part.from_text(text=prompt))

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=types.Content(parts=parts, role="user"),
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=2000,
                ),
            )
            text = response.text.strip()
            # Extract JSON from possible markdown fences
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(text)
            analysis_list = parsed.get("images", [])
            analysis_by_idx = {a["index"]: a for a in analysis_list}

            for j, img in enumerate(batch):
                if j in analysis_by_idx:
                    a = analysis_by_idx[j]
                    img["style_name"] = a.get("style_name", img.get("title", ""))[:40]
                    img["trend_score"] = max(1, min(10, a.get("trend_score", 5)))
                    img["is_clean_photo"] = a.get("is_clean_photo", True)
                    img["description"] = a.get("description", "")
                    img["suitable_age"] = a.get("suitable_age", "")
                    img["keywords"] = a.get("keywords", [])
                else:
                    _fill_defaults_single(img)
        except Exception:
            _fill_defaults(batch)

    return images


def _fill_defaults(items):
    for img in items:
        _fill_defaults_single(img)


def _fill_defaults_single(img):
    img.setdefault("style_name", img.get("title", "스타일 미분류")[:30])
    img.setdefault("trend_score", 5)
    img.setdefault("description", "")
    img.setdefault("suitable_age", "")
    img.setdefault("keywords", [])


# ---------------------------------------------------------------------------
# 5. Score badge
# ---------------------------------------------------------------------------

def score_badge(score):
    if score >= 8:
        return "🔥 높음"
    elif score >= 5:
        return "⭐ 보통"
    else:
        return "💡 신규"


# ---------------------------------------------------------------------------
# Main search pipeline
# ---------------------------------------------------------------------------

def run_search(category, num_images, custom_query=""):
    """Execute full pipeline: keywords -> images -> Gemini analysis."""
    progress = st.progress(0, text="키워드 수집 중...")

    # Step 1: Keywords
    if custom_query:
        keywords = [custom_query]
    else:
        keywords = get_trending_keywords(category)
    st.session_state.trend_keywords = keywords
    progress.progress(15, text=f"키워드 {len(keywords)}개 수집 완료")

    if not keywords:
        st.error("키워드를 찾을 수 없습니다.")
        progress.empty()
        return

    # Step 2: Image search
    all_images = []
    per_kw = max(3, num_images // len(keywords))

    for idx, kw in enumerate(keywords):
        pct = 15 + int(50 * (idx + 1) / len(keywords))
        progress.progress(pct, text=f"이미지 검색 중... ({kw})")
        imgs = search_images(kw, per_kw)
        for img in imgs:
            img["search_keyword"] = kw
            img["category"] = category
        all_images.extend(imgs)

    # Deduplicate by URL
    seen_urls = set()
    unique_images = []
    for img in all_images:
        if img["url"] and img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            unique_images.append(img)
    unique_images = unique_images[:num_images]

    if not unique_images:
        st.error("이미지를 찾을 수 없습니다. API 키를 확인하거나 다른 카테고리를 시도해주세요.")
        progress.empty()
        return

    progress.progress(70, text=f"이미지 {len(unique_images)}개 수집 완료. Gemini 분석 중...")

    # Step 3: Gemini analysis
    analyzed = analyze_images_with_gemini(unique_images)

    # Filter out thumbnails/collages (is_clean_photo == False)
    clean_count = len(analyzed)
    analyzed = [img for img in analyzed if img.get("is_clean_photo", True)]
    filtered_count = clean_count - len(analyzed)
    if filtered_count > 0:
        st.info(f"썸네일/콜라주 {filtered_count}개 자동 제외됨")

    # Sort by trend score descending
    analyzed.sort(key=lambda x: x.get("trend_score", 0), reverse=True)

    progress.progress(100, text="완료!")
    time.sleep(0.3)
    progress.empty()

    st.session_state.trend_results = analyzed
    st.session_state.show_favorites = False


# ---------------------------------------------------------------------------
# UI — Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("💇 트렌드 검색 설정")

    category = st.selectbox(
        "카테고리",
        list(CATEGORIES.keys()) + ["커스텀 검색"],
        index=0,
    )

    custom_query = ""
    if category == "커스텀 검색":
        custom_query = st.text_input("검색어 입력", placeholder="예: 2025 히피펌 트렌드")

    num_images = st.slider("이미지 수", min_value=10, max_value=40, value=20, step=5)
    col_count = st.select_slider("갤러리 열 수", options=[3, 4, 5], value=4)

    if st.button("🔍 검색", type="primary", use_container_width=True):
        if category == "커스텀 검색" and not custom_query:
            st.warning("검색어를 입력해주세요.")
        else:
            run_search(category, num_images, custom_query)

    # API status
    st.divider()
    st.caption("**API 상태**")
    st.caption(f"Google Search: {'✅' if GOOGLE_API_KEY and GOOGLE_CX else '❌ (DDG 대체)'}")
    st.caption(f"Gemini Vision: {'✅' if GEMINI_API_KEY else '❌ (분석 없음)'}")

    # Favorites section
    st.divider()
    st.subheader("⭐ 즐겨찾기")
    fav_count = len(st.session_state.favorites)
    st.caption(f"{fav_count}개 저장됨")

    if fav_count > 0:
        if st.button("즐겨찾기 보기", use_container_width=True):
            st.session_state.show_favorites = True
            st.rerun()
        for idx, fav in enumerate(st.session_state.favorites):
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.caption(fav.get("style_name", fav.get("title", ""))[:25])
                with c2:
                    if st.button("❌", key=f"rm_fav_{idx}"):
                        remove_favorite(fav["url"])
                        st.rerun()
    else:
        st.caption("즐겨찾기가 비어있습니다.")

    # Reference image status in sidebar
    if st.session_state.selected_reference:
        st.divider()
        st.success("📋 레퍼런스 이미지 선택됨")
        ref = st.session_state.selected_reference
        ref_bytes = ref.get("image_bytes")
        if ref_bytes:
            ref_pil = bytes_to_pil(ref_bytes)
            if ref_pil:
                st.image(ref_pil, caption=ref.get("style_name", ""), use_container_width=True)
        if st.button("레퍼런스 해제", use_container_width=True):
            st.session_state.selected_reference = None
            st.rerun()


# ---------------------------------------------------------------------------
# UI — Main area
# ---------------------------------------------------------------------------

st.title("💇 트렌드 헤어 갤러리")
st.caption("Google Trends + Gemini Vision 기반 실시간 헤어스타일 트렌드")

# API setup instructions (collapsible)
if not GOOGLE_API_KEY or not GOOGLE_CX:
    with st.expander("ℹ️ Google Custom Search API 설정 방법 (선택사항)", expanded=False):
        st.markdown("""
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **Custom Search JSON API** 활성화
3. [Programmable Search Engine](https://programmablesearchengine.google.com/)에서 검색엔진 생성
   - "전체 웹 검색" 활성화, "이미지 검색" 활성화
4. 환경변수 설정:
   ```
   GOOGLE_API_KEY=your_api_key
   GOOGLE_CX=your_search_engine_id
   ```
> **API 키 없이도 DuckDuckGo 이미지 검색으로 동작합니다.**
        """)

if not GEMINI_API_KEY:
    with st.expander("ℹ️ Gemini API 설정 방법 (선택사항)", expanded=False):
        st.markdown("""
1. [Google AI Studio](https://aistudio.google.com/)에서 API 키 발급
2. 환경변수 설정:
   ```
   GEMINI_API_KEY=your_api_key
   ```
> **API 키 없이도 이미지 갤러리는 표시되지만, AI 스타일 분석은 생략됩니다.**
        """)

# --- Favorites view ---
if st.session_state.show_favorites:
    st.subheader("⭐ 즐겨찾기 이미지")

    if not st.session_state.favorites:
        st.info("저장된 즐겨찾기가 없습니다.")
    else:
        fav_cols = st.columns(col_count)
        displayed = 0
        for i, fav in enumerate(st.session_state.favorites):
            raw = download_image_bytes(fav["url"])
            if raw is None:
                continue
            pil = bytes_to_pil(raw)
            if pil is None:
                continue

            col = fav_cols[displayed % col_count]
            with col:
                st.image(pil, use_container_width=True)
                st.markdown(f"**{fav.get('style_name', fav.get('title', ''))[:30]}**")
                if fav.get("trend_score"):
                    st.caption(f"{score_badge(fav['trend_score'])} ({fav['trend_score']}/10)")
                st.caption(f"📂 {fav.get('category', '')}")

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("🗑️ 삭제", key=f"delfav_{i}"):
                        remove_favorite(fav["url"])
                        st.rerun()
                with bc2:
                    if st.button("📋 참조용", key=f"reffav_{i}"):
                        st.session_state.selected_reference = {
                            "url": fav["url"],
                            "style_name": fav.get("style_name", ""),
                            "image_bytes": raw,
                        }
                        st.rerun()
                st.divider()
                displayed += 1

    if st.button("← 검색 결과로 돌아가기"):
        st.session_state.show_favorites = False
        st.rerun()

# --- Search results view ---
elif st.session_state.trend_results:
    # Step 1: Keywords
    if st.session_state.trend_keywords:
        with st.expander("📊 Step 1: 수집된 트렌드 키워드", expanded=False):
            kw_count = len(st.session_state.trend_keywords)
            kw_cols = st.columns(min(5, kw_count))
            for i, kw in enumerate(st.session_state.trend_keywords):
                with kw_cols[i % len(kw_cols)]:
                    st.markdown(f"`{kw}`")

    # Step 2: Gallery
    results = st.session_state.trend_results
    st.subheader(f"📸 Step 2: 트렌드 갤러리 ({len(results)}개)")

    cols = st.columns(col_count)
    displayed = 0

    for idx, item in enumerate(results):
        raw = download_image_bytes(item["url"])
        if raw is None:
            continue
        pil = bytes_to_pil(raw)
        if pil is None:
            continue

        col = cols[displayed % col_count]
        with col:
            st.image(pil, use_container_width=True)

            score = item.get("trend_score", 5)
            style_name = item.get("style_name", item.get("title", ""))[:35]
            badge = score_badge(score)

            st.markdown(f"**{style_name}**")
            st.caption(f"{badge} ({score}/10)")

            if item.get("description"):
                st.caption(item["description"][:60])

            if item.get("suitable_age"):
                st.caption(f"👤 {item['suitable_age']}")

            # Action buttons
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                is_fav = any(f["url"] == item["url"] for f in st.session_state.favorites)
                if is_fav:
                    if st.button("💛", key=f"unfav_{idx}", help="즐겨찾기 해제"):
                        remove_favorite(item["url"])
                        st.rerun()
                else:
                    if st.button("⭐", key=f"fav_{idx}", help="즐겨찾기 추가"):
                        add_favorite(item)
                        st.rerun()
            with btn_c2:
                if st.button("📋", key=f"ref_{idx}", help="레퍼런스로 사용"):
                    st.session_state.selected_reference = {
                        "url": item["url"],
                        "style_name": item.get("style_name", ""),
                        "image_bytes": raw,
                    }
                    # Also store in reference_image_url for main app compatibility
                    st.session_state.reference_image_url = item["url"]
                    st.rerun()

            st.divider()
            displayed += 1

    if displayed == 0:
        st.warning("표시할 수 있는 이미지가 없습니다. 다른 카테고리를 시도해주세요.")

# --- Empty state ---
else:
    st.info("👈 왼쪽 사이드바에서 카테고리를 선택하고 🔍 검색 버튼을 눌러주세요.")

    # Quick start buttons
    st.markdown("### 빠른 검색")
    quick_cols = st.columns(4)
    quick_cats = ["20대 여성", "30대 여성", "20대 남성", "40대 여성"]
    for i, qc in enumerate(quick_cats):
        with quick_cols[i]:
            if st.button(f"💇 {qc}", key=f"quick_{i}", use_container_width=True):
                run_search(qc, 20)
                st.rerun()
