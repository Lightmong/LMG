import streamlit as st
import requests
import json
import os
from PIL import Image
from google import genai
from google.genai import types
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

# 하얀색 배경, 스티일링 및 모바일 최우선 CSS 설정
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
    
    /* 좌상단 다른 사물 찾아보기 버튼 스타일 override */
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
# 3. Helper Functions (AI Vision & PubChem DB API)
# -----------------------------------------------------------------------------
def analyze_image_with_gemini(image):
    """Computer Vision 기반 객체 인식 및 대표 화학 성분 추정"""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error("GEMINI_API_KEY가 설정되지 않았습니다. Secrets를 확인해주세요.")
        return None

    client = genai.Client(api_key=api_key)

    prompt = """
    이 사진 속의 주요 사물을 인식하고, 그 사물을 대표하는 가장 주요한 화학 성분(분자) 1개를 추정해주세요.
    학생들이 친숙하게 화학식을 배울 수 있도록 설명해야 합니다.
    
    반드시 아래의 JSON 포맷으로만 응답해주세요. 설명이나 마크다운 태그 없이 pure JSON으로만 응답해야 합니다.
    
    {
      "object_name": "인식된 사물 이름 (예: 물병, 사과, 연필)",
      "compound_name_ko": "화학물질 한국어명 (예: 물, 과당, 그래핀)",
      "compound_name_en": "PubChem 검색용 영문 화학물질명 (예: Water, Fructose, Graphite)",
      "chemical_formula": "화학식 (예: H2O, C6H12O6, C)",
      "other_examples": [
        {
          "name": "같은 성분이 들어있는 다른 사물 1",
          "image_keyword": "unsplash 검색용 영어 단어 (예: ice)"
        },
        {
          "name": "같은 성분이 들어있는 다른 사물 2",
          "image_keyword": "unsplash 검색용 영어 단어 (예: rain)"
        }
      ]
    }
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"이미지 분석 중 오류가 발생했습니다: {e}")
        return None

def fetch_pubchem_sdf(compound_name):
    """PubChem 데이터베이스에서 3D 구조 SDF 데이터 가져오기"""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{compound_name}/SDF?record_type=3d"
        res = requests.get(url, timeout=5)
        if res.status_status_code == 200 and res.text.strip():
            return res.text
        # 3D 구조가 없으면 2D 구조 시도
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
    
    # 원자별 고유 색상(CPK Color Standard) 반영 및 구-막대(Stick+Sphere) 스타일
    view.setStyle({'stick': {'radius': 0.15}, 'sphere': {'scale': 0.25}})
    view.zoomTo()
    return view

# -----------------------------------------------------------------------------
# 4. App Screen Layouts
# -----------------------------------------------------------------------------

# --- [시작 화면] ---
if st.session_state.stage == 'start':
    st.markdown('<div class="title-text">성분돋보기</div>', unsafe_allow_html=True)
    
    # 정 가운데 위치 배치를 위한 여백
    st.write("##")
    st.write("##")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # 사진 촬영/업로드 버튼 (모바일 호환)
        uploaded_file = st.file_uploader(
            "사진 촬영 및 분석", 
            type=["jpg", "jpeg", "png"],
            label_visibility="collapsed"
        )
        
        # 버튼 스타일을 적용한 모의 UI 및 액션 Trigger
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
        # 정 가운데 회전하는 애니메이션 / 로딩 표출
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
    
    # 백그라운드 분석 실행
    if st.session_state.get('uploaded_image'):
        result_json = analyze_image_with_gemini(st.session_state.uploaded_image)
        if result_json:
            sdf_data = fetch_pubchem_sdf(result_json.get('compound_name_en', ''))
            st.session_state.analysis_data = {
                'info': result_json,
                'sdf': sdf_data
            }
            st.session_state.stage = 'result'
            st.rerun()
        else:
            st.session_state.stage = 'start'
            st.rerun()

# --- [분석 완료 화면] ---
elif st.session_state.stage == 'result':
    data = st.session_state.analysis_data
    info = data['info']
    sdf = data['sdf']
    
    # 상단 헤더 영역 (좌: 재촬영 버튼, 우: 타이틀)
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

    # 메인 콘텐츠 영역 (좌: 분자식 및 3D 모형, 우: 이 분자식이 있는 다른 사물)
    main_col1, main_col2 = st.columns([3, 2])

    with main_col1:
        # 분자식 검은색 글씨 표시 및 안내
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 15px;">
                <h2 style="color: #000000; margin:0;">{info.get('compound_name_ko')} ({info.get('chemical_formula')})</h2>
                <p style="color: #333333; font-size: 0.95rem;">마우스로 분자를 직접 클릭하여 360도 회전시켜 보세요!</p>
            </div>
        """, unsafe_allow_html=True)

        # 3D 분자 구조식 상호작용 렌더링
        if sdf:
            view = render_3d_molecule(sdf)
            stmol.showfree(view, height=350, width=400)
        else:
            st.warning("분자 3D 구조 데이터를 불러오지 못했습니다.")

    with main_col2:
        # 우상단 다른 사물 안내
        st.markdown("""
            <h4 style="color: #000000; margin-bottom: 15px; font-weight: bold;">
                이 분자식이 있는 다른 사물
            </h4>
        """, unsafe_allow_html=True)

        examples = info.get('other_examples', [])
        for ex in examples:
            ex_name = ex.get('name', '예시 사물')
            keyword = ex.get('image_keyword', 'object')
            # Unsplash Source API를 이용해 관련 예시 이미지 노출
            img_url = f"https://source.unsplash.com/300x200/?{keyword}"

            st.write(f"**• {ex_name}**")
            st.image(img_url, use_column_width=True)

# -----------------------------------------------------------------------------
# 5. Footer Disclaimer (Do 제약조건 필수 항목)
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="disclaimer">
        본 결과는 AI 기반 추정치이며 실제와 다를 수 있습니다.
    </div>
""", unsafe_allow_html=True)
