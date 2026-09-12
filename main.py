import streamlit as st
import requests
import json
import io
import re
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

# 사물 키워드에 따른 화학 성분 매칭 사전 (교육용 매핑 데이터베이스)
OBJECT_TO_CHEMICAL_DB = {
    "water": {
        "object_ko": "물병 / 물",
        "compound_ko": "물",
        "compound_en": "Water",
        "formula": "H₂O",
        "examples": [
            {"name": "얼음", "keyword": "ice"},
            {"name": "비", "keyword": "rain"}
        ]
    },
    "apple": {
        "object_ko": "사과",
        "compound_ko": "과당 (Fructose)",
        "compound_en": "Fructose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {"name": "꿀", "keyword": "honey"},
            {"name": "포도", "keyword": "grapes"}
        ]
    },
    "pencil": {
        "object_ko": "연필",
        "compound_ko": "흑연 (탄소)",
        "compound_en": "Graphite",
        "formula": "C",
        "examples": [
            {"name": "다이아몬드", "keyword": "diamond"},
            {"name": "숯", "keyword": "charcoal"}
        ]
    },
    "bottle": {
        "object_ko": "플라스틱 병",
        "compound_ko": "폴리에틸렌 테레프탈레이트 (PET)",
        "compound_en": "Polyethylene terephthalate",
        "formula": "(C₁₀H₈O₄)n",
        "examples": [
            {"name": "합성섬유 옷", "keyword": "polyester clothes"},
            {"name": "포장용 용기", "keyword": "plastic container"}
        ]
    },
    "default": {
        "object_ko": "일반 유기물 사물",
        "compound_ko": "포도당 (Glucose)",
        "compound_en": "Glucose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {"name": "빵", "keyword": "bread"},
            {"name": "쌀밥", "keyword": "rice"}
        ]
    }
}

def query_huggingface_vision(image):
    """Hugging Face Inference API를 사용해 이미지 속 사물 분석"""
    hf_token = st.secrets.get("HF_TOKEN")
    if not hf_token:
        st.error("HF_TOKEN이 설정되지 않았습니다. Secrets 구성을 확인해주세요.")
        return None

    # BLIP Image Captioning 모델 (무료 지원 모델)
    API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"
    headers = {"Authorization": f"Bearer {hf_token}"}

    # 이미지 파일 버퍼 변환
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
    """인식된 키워드를 기반으로 화학 성분 및 데이터 매칭"""
    caption = query_huggingface_vision(image)
    if not caption:
        matched_data = OBJECT_TO_CHEMICAL_DB["default"]
    else:
        # 키워드 필터링 매칭
        matched_data = OBJECT_TO_CHEMICAL_DB["default"]
        for key in OBJECT_TO_CHEMICAL_DB:
            if key in caption:
                matched_data = OBJECT_TO_CHEMICAL_DB[key]
                break

    return matched_data

def fetch_pubchem_sdf(compound_name):
    """PubChem 데이터베이스에서 3D 구조 SDF 데이터 가져오기"""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/SDF?record_type=3d"
        res = requests.get(url, timeout=5)
        if res.status_code == 200 and res.text.strip():
            return res.text
        # 3D 구조가 없을 경우 2D 구조 요청
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
    
    # 원자별 고유 색상(CPK Color Standard) 및 Stick+Sphere 스타일 적용
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
    st.write("##")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # 사진 촬영/업로드 버튼 (모바일 겸용)
        uploaded_file = st.file_uploader(
            "사진 촬영 및 분석", 
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
        # 검은색 회전 화살표 애니메이션 및 메시지
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
    
    # 분석 실행
    if st.session_state.get('uploaded_image'):
        chemical_info = process_image_analysis(st.session_state.uploaded_image)
        sdf_data = fetch_pubchem_sdf(chemical_info['compound_en'])
        
        st.session_state.analysis_data = {
            'info': chemical_info,
            'sdf': sdf_data
        }
        st.session_state.stage = 'result'
        st.rerun()

# --- [분석 완료 화면] ---
elif st.session_state.stage == 'result':
    data = st.session_state.analysis_data
    info = data['info']
    sdf = data['sdf']
    
    # 상단 버튼 및 제목
    top_col1, top_col2 = st.columns([1, 2])
    with top_col1:
        st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
        if st.button("다른 사물 찾아보기"):
            st.session_state.stage = 'start'
            st.session_state.analysis_data = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="title-text" style="margin-top:-20px;">성분돋보기</div>', unsafe_allow_html=True)
    st.divider()

    # 메인 분석 결과 (좌: 3D 분자 모형, 우: 이 분자식이 있는 다른 사물 예시)
    main_col1, main_col2 = st.columns([3, 2])

    with main_col1:
        # 분자식 검은색 글씨 표시
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 15px;">
                <h2 style="color: #000000; margin:0;">{info.get('compound_ko')} ({info.get('formula')})</h2>
                <p style="color: #333333; font-size: 0.95rem;">마우스나 손가락으로 분자 모형을 돌려보세요!</p>
            </div>
        """, unsafe_allow_html=True)

        # 3D 분자 구조식 상호작용 렌더링
        if sdf:
            view = render_3d_molecule(sdf)
            stmol.showfree(view, height=350, width=400)
        else:
            st.warning("PubChem 데이터베이스에서 분자 3D 구도를 불러올 수 없습니다.")

    with main_col2:
        # 우상단 다른 사물 표시
        st.markdown("""
            <h4 style="color: #000000; margin-bottom: 15px; font-weight: bold;">
                이 분자식이 있는 다른 사물
            </h4>
        """, unsafe_allow_html=True)

        examples = info.get('examples', [])
        for ex in examples:
            ex_name = ex.get('name', '예시 사물')
            keyword = ex.get('keyword', 'object')
            
            # Wikimedia / Unsplash 기반 예시 이미지 노출
            img_url = f"https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?w=300" if keyword == "ice" else f"https://source.unsplash.com/300x200/?{keyword}"

            st.write(f"**• {ex_name}**")
            st.image(f"https://picsum.photos/seed/{keyword}/300/200", use_column_width=True)

# -----------------------------------------------------------------------------
# 5. Footer Disclaimer (Do 제약조건 필수 항목)
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="disclaimer">
        본 결과는 AI 기반 추정치이며 실제와 다를 수 있습니다.
    </div>
""", unsafe_allow_html=True)
