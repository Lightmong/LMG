import streamlit as st
import requests
import json
import io
from PIL import Image
import stmol
import py3Dmol

# -----------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS
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

    /* 결과 요약 상자 스타일 */
    .result-box {
        background-color: #F8F9FA;
        border-radius: 12px;
        padding: 18px;
        border: 1px solid #E9ECEF;
        margin-bottom: 20px;
        text-align: center;
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
# 3. Helper Functions & Chemical Database
# -----------------------------------------------------------------------------

# 키워드별 세분화된 사물 및 화학 성분 DB
OBJECT_TO_CHEMICAL_DB = {
    "water": {
        "keywords": ["water", "liquid", "drink", "cup", "glass", "beverage", "bottle of water"],
        "object_ko": "물 / 수분 음료",
        "compound_ko": "물 (Water)",
        "compound_en": "Water",
        "formula": "H₂O",
        "examples": [
            {
                "name": "각얼음 (Ice Cubes)", 
                "image_url": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "빗물 (Raindrops)", 
                "image_url": "https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "coffee": {
        "keywords": ["coffee", "mug", "espresso", "tea", "caffeine"],
        "object_ko": "커피 / 차",
        "compound_ko": "카페인 (Caffeine)",
        "compound_en": "Caffeine",
        "formula": "C₈H₁₀N₄O₂",
        "examples": [
            {
                "name": "녹차 (Green Tea)", 
                "image_url": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "에스프레소 커피", 
                "image_url": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "apple": {
        "keywords": ["apple", "fruit", "orange", "banana", "sweet", "strawberry"],
        "object_ko": "과일 / 천연 당분",
        "compound_ko": "과당 (Fructose)",
        "compound_en": "Fructose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {
                "name": "천연 꿀 (Honey)", 
                "image_url": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "포도 (Grapes)", 
                "image_url": "https://images.unsplash.com/photo-1537640538966-79f369143f8f?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "paper": {
        "keywords": ["paper", "book", "box", "cardboard", "wood", "table", "notebook"],
        "object_ko": "종이 / 목재류",
        "compound_ko": "셀룰로오스 (Cellulose)",
        "compound_en": "Cellulose",
        "formula": "(C₆H₁₀O₅)n",
        "examples": [
            {
                "name": "면 옷 (Cotton)", 
                "image_url": "https://images.unsplash.com/photo-1521572267360-ee0c2909d518?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "책 / 종이 (Books)", 
                "image_url": "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "salt": {
        "keywords": ["salt", "white powder", "seasoning", "dish", "plate"],
        "object_ko": "소금 / 조미료",
        "compound_ko": "염화 나트륨 (Sodium Chloride)",
        "compound_en": "Sodium chloride",
        "formula": "NaCl",
        "examples": [
            {
                "name": "바닷물 (Sea Water)", 
                "image_url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "소금 결정 (Salt)", 
                "image_url": "https://images.unsplash.com/photo-1626197031507-c170a04d2a09?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "pencil": {
        "keywords": ["pencil", "pen", "graphite", "black"],
        "object_ko": "연필 / 필기구",
        "compound_ko": "흑연 (Graphite / Carbon)",
        "compound_en": "Graphite",
        "formula": "C",
        "examples": [
            {
                "name": "숯 (Charcoal)", 
                "image_url": "https://images.unsplash.com/photo-1541781774459-bb2af2f05b55?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "다이아몬드 (Diamond)", 
                "image_url": "https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "bread": {
        "keywords": ["bread", "cake", "rice", "cookie", "noodle", "pasta", "food"],
        "object_ko": "빵 / 밥 / 탄수화물",
        "compound_ko": "녹말 (Starch)",
        "compound_en": "Starch",
        "formula": "(C₆H₁₀O₅)n",
        "examples": [
            {
                "name": "감자 (Potatoes)", 
                "image_url": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "옥수수 (Corn)", 
                "image_url": "https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=500&auto=format&fit=crop&q=80"
            }
        ]
    },
    "default": {
        "keywords": [],
        "object_ko": "설탕 / 단 음식",
        "compound_ko": "포도당 (Glucose)",
        "compound_en": "Glucose",
        "formula": "C₆H₁₂O₆",
        "examples": [
            {
                "name": "백설탕 (White Sugar)", 
                "image_url": "https://images.unsplash.com/photo-1622484210800-4183d29a531f?w=500&auto=format&fit=crop&q=80"
            },
            {
                "name": "과일 잼 (Fruit Jam Jar)", 
                "image_url": "https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?w=500&auto=format&fit=crop&q=80"
            }
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
    """인식된 영문 문장에서 매칭되는 사물 및 화학 성분 검색"""
    caption = query_huggingface_vision(image)
    
    if not caption:
        return OBJECT_TO_CHEMICAL_DB["default"], "인식 불가"

    matched_data = None
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
    """Py3Dmol을 이용한 3D 분자 모형 렌더링"""
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
                    사물 및 화학 성분을 분석 중입니다...
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
    
    # [1] AI가 인식한 사물 및 [2] 화학 성분/분자식 안내 요약 상자
    st.markdown(f"""
        <div class="result-box">
            <span style="color: #555555; font-size: 0.95rem;">📷 인식된 사물:</span>
            <strong style="color: #000000; font-size: 1.1rem; margin-right: 15px;"> {info.get('object_ko')}</strong>
            <br>
            <span style="color: #555555; font-size: 0.95rem;">🧪 대표 화학 성분:</span>
            <strong style="color: #0066CC; font-size: 1.2rem;"> {info.get('compound_ko')} [{info.get('formula')}]</strong>
        </div>
    """, unsafe_allow_html=True)

    main_col1, main_col2 = st.columns([3, 2])

    with main_col1:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 10px;">
                <h3 style="color: #000000; margin:0;">3D 분자 구조 모형</h3>
                <p style="color: #666666; font-size: 0.85rem;">마우스나 터치로 돌려볼 수 있습니다.</p>
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
            img_url = ex.get('image_url')
            
            st.markdown(f"**• {ex_name}**")
            if img_url:
                st.image(img_url, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. Footer Disclaimer
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="disclaimer">
        본 결과는 AI 기반 추정치이며 실제와 다를 수 있습니다.
    </div>
""", unsafe_allow_html=True)
