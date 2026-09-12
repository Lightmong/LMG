import streamlit as st
import requests
import json
import io
from PIL import Image
import stmol
import py3Dmol

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS (UI Requirements)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="성분돋보기",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 하얀색 배경, 모바일 최우선 UI 스타일링
st.markdown("""
    <style>
    /* 전체 배경을 하얀색으로 고정 */
    .stApp {
        background-color: #FFFFFF;
        color: #000000;
    }
    
    /* 상단 검은색 제목 */
    .title-text {
        color: #000000;
        text-align: center;
        font-size: 2.2rem;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 20px;
    }

    /* 하늘색 버튼 스타일 */
    div.stButton > button:first-child {
        background-color: #87CEEB !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 28px !important;
        font-size: 1.1rem !important;
        font-weight: bold !important;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1) !important;
    }
    
    /* 좌상단 다른 사물 찾아보기 버튼 스타일 */
    .reset-btn div.stButton > button:first-child {
        background-color: #F0F0F0 !important;
        color: #000000 !important;
        border: 1px solid #CCCCCC !important;
        padding: 6px 14px !important;
        font-size: 0.9rem !important;
    }

    /* 하단 면책 조항 */
    .disclaimer {
        position: fixed;
        bottom: 10px;
        left: 0;
        width: 100%;
        text-align: center;
        font-size: 0.8rem;
        color: #666666;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 5px 0;
        z-index: 999;
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Session State Management
# -----------------------------------------------------------------------------
if 'stage' not in st.session_state:
    st.session_state.stage = 'start'  # 'start', 'analyzing', 'result'
if 'analysis_data' not in st.session_state:
    st.session_state.analysis_data = None

# -----------------------------------------------------------------------------
# 3. Helper Functions (Hugging Face Vision AI & Chemical Mapping)
# -----------------------------------------------------------------------------

# 사물 키워드 및 다양한 카테고리별 화학 성분 매칭 데이터베이스 (확장 버전)
OBJECT_TO_CHEMICAL_DB = {
    "water": {
        "keywords": ["water", "liquid", "drink", "cup", "glass", "beverage"],
        "object_ko": "물 / 음료수",
        "compound_ko": "물 (Water)",
        "compound_en": "Water",
        "formula": "H₂O",
        "examples": [
            {"name": "얼음", "keyword": "ice"},
            {"name": "비", "keyword": "rain"}
        ]
    },
    "coffee": {
        "keywords": ["coffee", "mug", "espresso", "tea"],
        "object_ko": "커피 / 차",
        "compound_ko": "카페인 (Caffeine)",
        "compound_en": "Caffeine",
        "formula": "C₈H₁₀N₄O₂",
        "examples": [
            {"name": "녹차", "keyword": "green tea"},
            {"name": "에너지 음료", "keyword": "energy drink"}
        ]
    },
    "apple": {
        "keywords": ["apple", "fruit", "orange", "banana", "sweet"],
        "object_ko": "과일 / 단 음식",
        "compound_ko": "과당 (Fructose)",
        "compound_en": "Fructose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {"name": "꿀", "keyword": "honey"},
            {"name": "포도", "keyword": "grapes"}
        ]
    },
    "paper": {
        "keywords": ["paper", "book", "box", "cardboard", "wood", "table"],
        "object_ko": "종이 / 나무 제품",
        "compound_ko": "셀룰로오스 (Cellulose)",
        "compound_en": "Cellulose",
        "formula": "(C₆H₁₀O₅)n",
        "examples": [
            {"name": "면 옷", "keyword": "cotton shirt"},
            {"name": "휴지", "keyword": "tissue paper"}
        ]
    },
    "salt": {
        "keywords": ["salt", "white powder", "food", "dish", "plate"],
        "object_ko": "소금 / 음료",
        "compound_ko": "염화 나트륨 (Sodium Chloride)",
        "compound_en": "Sodium chloride",
        "formula": "NaCl",
        "examples": [
            {"name": "해수 (바닷물)", "keyword": "sea water"},
            {"name": "생리식염수", "keyword": "saline solution"}
        ]
    },
    "pencil": {
        "keywords": ["pencil", "pen", "black"],
        "object_ko": "연필 / 흑연",
        "compound_ko": "흑연 (탄소)",
        "compound_en": "Graphite",
        "formula": "C",
        "examples": [
            {"name": "다이아몬드", "keyword": "diamond"},
            {"name": "숯", "keyword": "charcoal"}
        ]
    },
    "bottle": {
        "keywords": ["bottle", "plastic", "container"],
        "object_ko": "플라스틱 용기",
        "compound_ko": "폴리에틸렌 테레프탈레이트 (PET)",
        "compound_en": "Polyethylene terephthalate",
        "formula": "(C₁₀H₈O₄)n",
        "examples": [
            {"name": "합성섬유 옷", "keyword": "polyester clothes"},
            {"name": "비닐봉지", "keyword": "plastic bag"}
        ]
    },
    "bread": {
        "keywords": ["bread", "cake", "rice", "food", "cookie"],
        "object_ko": "빵 / 밥 / 곡물",
        "compound_ko": "녹말 (Starch)",
        "compound_en": "Starch",
        "formula": "(C₆H₁₀O₅)n",
        "examples": [
            {"name": "감자", "keyword": "potato"},
            {"name": "옥수수", "keyword": "corn"}
        ]
    },
    "default": {
        "keywords": [],
        "object_ko": "일반 유기물 사물",
        "compound_ko": "포도당 (Glucose)",
        "compound_en": "Glucose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {"name": "설탕", "keyword": "sugar"},
            {"name": "과일 잼", "keyword": "jam"}
        ]
    }
}

def query_huggingface_vision(image):
    """Hugging Face Inference API를 사용해 이미지 속 사물 분석"""
    hf_token = st.secrets.get("HF_TOKEN")
    if not hf_token:
        st.error("HF_TOKEN이 설정되지 않았습니다. Secrets 구성을 확인해주세요.")
        return None

    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    headers = {"Authorization": f"Bearer {hf_token}"}

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    try:
        response = requests.post(API_URL, headers=headers, data=img_bytes, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                caption = result[0].get("generated_text", "").lower()
                return caption
        return None
    except Exception as e:
        st.error(f"이미지 인식 중 오류가 발생했습니다: {e}")
        return None

def process_image_analysis(image):
    """인식된 캡션 단어를 기반으로 화학 성분 및 데이터 매칭"""
    caption = query_huggingface_vision(image)
    
    if not caption:
        return OBJECT_TO_CHEMICAL_DB["default"], "인식 불가 (기본값)"

    matched_data = None
    # 캡션 문장에 포함된 키워드 검색
    for key, data in OBJECT_TO_CHEMICAL_DB.items():
        if key == "default":
            continue
        for kw in data["keywords"]:
            if kw in caption:
                matched_data = data
                break
        if matched_data:
            break

    if not matched_data:
        matched_data = OBJECT_TO_CHEMICAL_DB["default"]

    return matched_data, caption

def fetch_pubchem_sdf(compound_name):
    """PubChem 데이터베이스에서 3D 구조 SDF 데이터 가져오기"""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/SDF?record_type=3d"
        res = requests.get(url, timeout=5)
        if res.status_code == 200 and res.text.strip():
            return res.text
        url_2d = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/SDF"
        res_2d = requests.get(url_2d, timeout=5)
        if res_2d.status_code == 200:
            return res_2d.text
        return None
    except:
        return None

def render_3d_molecule(sdf_data):
    """Py3Dmol을 이용해 원자별 고유 색상이 적용된 상호작용 3D 분자 모형 렌더링"""
    view = py3Dmol.view(width=400, height=350)
    view.addModel(sdf_data, 'sdf')
    view.setStyle({'stick': {'radius': 0.15}, 'sphere': {'scale': 0.25}})
    view.zoomTo()
    return view

# -----------------------------------------------------------------------------
# 4. App Screen Layouts
# -----------------------------------------------------------------------------

# --- [시작 화면] ---
if st.session_state.stage == 'start':
    st.markdown('<div class="title-text">성분돋보기</div>', unsafe_allow_html=True)
    
    st.write("##")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["📸 사진 촬영하기", "📁 파일 선택하기"])
        
        with tab1:
            camera_file = st.camera_input("사물을 카메라로 촬영하세요", label_visibility="collapsed")
            if camera_file is not None:
                st.session_state.uploaded_image = Image.open(camera_file)
                st.session_state.stage = 'analyzing'
                st.rerun()

        with tab2:
            uploaded_file = st.file_uploader(
                "사진 파일 선택", 
                type=["jpg", "jpeg", "png"],
                label_visibility="collapsed"
            )
            if uploaded_file is not None:
                st.session_state.uploaded_image = Image.open(uploaded_file)
                st.session_state.stage = 'analyzing'
                st.rerun()

# --- [분석 중 화면] ---
elif st.session_state.stage == 'analyzing':
    st.markdown('<div class="title-text">성분돋보기</div>', unsafe_allow_html=True)
    st.write("##")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("""
            <div style="text-align: center; margin-top: 40px;">
                <div style="
                    display: inline-block;
                    width: 50px;
                    height: 50px;
                    border: 5px solid #E0E0E0;
                    border-top: 5px solid #000000;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
                <p style="color: #000000; font-size: 1.2rem; font-weight: bold; margin-top: 20px;">
                    분석 중입니다...
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    if st.session_state.get('uploaded_image'):
        chemical_info, caption = process_image_analysis(st.session_state.uploaded_image)
        sdf_data = fetch_pubchem_sdf(chemical_info['compound_en'])
        
        st.session_state.analysis_data = {
            'info': chemical_info,
            'caption': caption,
            'sdf': sdf_data
        }
        st.session_state.stage = 'result'
        st.rerun()

# --- [분석 완료 화면] ---
elif st.session_state.stage == 'result':
    data = st.session_state.analysis_data
    info = data['info']
    caption = data.get('caption', '')
    sdf = data['sdf']
    
    top_col1, top_col2 = st.columns([1, 2])
    with top_col1:
        st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
        if st.button("다른 사물 찾아보기"):
            st.session_state.stage = 'start'
            st.session_state.analysis_data = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="title-text" style="margin-top:-20px;">성분돋보기</div>', unsafe_allow_html=True)
    st.caption(f"🤖 AI 인식 결과: `{caption}`")
    st.divider()

    main_col1, main_col2 = st.columns([3, 2])

    with main_col1:
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 15px;">
                <h2 style="color: #000000; margin:0;">{info.get('compound_ko')} ({info.get('formula')})</h2>
                <p style="color: #333333; font-size: 0.95rem;">마우스나 손가락으로 분자 모형을 직접 돌려보세요!</p>
            </div>
        """, unsafe_allow_html=True)

        if sdf:
            view = render_3d_molecule(sdf)
            stmol.showmol(view, height=350, width=400)
        else:
            st.warning("PubChem 데이터베이스에서 분자 3D 구도를 불러올 수 없습니다.")

    with main_col2:
        st.markdown("""
            <h4 style="color: #000000; margin-bottom: 15px; font-weight: bold;">
                이 분자식이 있는 다른 사물
            </h4>
        """, unsafe_allow_html=True)

        examples = info.get('examples', [])
        for ex in examples:
            ex_name = ex.get('name', '예시 사물')
            keyword = ex.get('keyword', 'object')
            
            st.write(f"**• {ex_name}**")
            st.image(f"https://picsum.photos/seed/{keyword}/300/200", use_container_width=True)

# -----------------------------------------------------------------------------
# 5. Footer Disclaimer
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="disclaimer">
        본 결과는 AI 기반 추정치이며 실제와 다를 수 있습니다.
    </div>
""", unsafe_allow_html=True)
