import streamlit as st
import google.generativeai as genai
import requests
import json
import base64

st.set_page_config(
    page_title="페르소나 메이커 챗봇",
    page_icon="🤖",
    layout="centered"
)

try:
    GEMINI_API_KEY = st.secrets["gemini_api_key"]
    IMAGEN_API_KEY = st.secrets.get("imagen_api_key", GEMINI_API_KEY)
except KeyError:
    st.error("API 키를 찾을 수 없습니다. `.streamlit/secrets.toml` 파일을 확인해주세요.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

CHAT_MODEL = genai.GenerativeModel('gemini-2.0-flash')

if "character_profile" not in st.session_state:
    st.session_state.character_profile = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "character_image_url" not in st.session_state:
    st.session_state.character_image_url = None
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "character_ready" not in st.session_state:
    st.session_state.character_ready = False

def _chat_avatar_for_role(role: str):
    if role == "model" and st.session_state.get("character_image_url"):
        return st.session_state.character_image_url
    return None

def generate_image(prompt):
    """
    [기능]: 입력된 텍스트 프롬프트를 기반으로 이미지를 생성합니다.
    [용어]: gemini-2.0-flash-preview-image-generation 모델을 사용하여 이미지를 생성합니다.
           API 호출은 `requests` 라이브러리를 사용합니다.
    """
    st.info("🎨 캐릭터 이미지를 생성 중입니다. 잠시만 기다려 주세요...")
    try:
        # gemini-2.0-flash-preview-image-generation 모델 API 엔드포인트
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent?key={IMAGEN_API_KEY}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            },
        }

        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

        result = response.json()
        
        # 응답에서 base64 인코딩된 이미지 데이터를 추출
        # Python에서 JavaScript 옵셔널 체이닝 '?' 문법은 사용할 수 없으므로, 직접 접근 방식과 예외 처리를 활용합니다.
        base64_data = None
        if result and result.get("candidates") and len(result["candidates"]) > 0:
            content = result["candidates"][0].get("content")
            if content and content.get("parts") and len(content["parts"]) > 0:
                for part in content["parts"]:
                    if part.get("inlineData"):
                        base64_data = part["inlineData"].get("data")
                        break
        
        if base64_data:
            image_url = f"data:image/png;base64,{base64_data}"
            st.session_state.character_image_url = image_url
            st.success("✨ 캐릭터 이미지가 성공적으로 생성되었습니다!")
            return image_url
        else:
            st.error("이미지 생성에 실패했습니다. 유효한 이미지 데이터가 반환되지 않았습니다.")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"이미지 생성 API 호출 중 오류 발생: {e}")
        return None
    except Exception as e:
        st.error(f"이미지 처리 중 오류 발생: {e}")
        return None

def create_character_and_chat_session():
    profile = st.session_state.input_profile
    story = st.session_state.input_story
    goals_pains = st.session_state.input_goals_pains
    behavior = st.session_state.input_behavior
    motivation = st.session_state.input_motivation

    if not all([profile, story, goals_pains, behavior, motivation]):
        st.warning("모든 캐릭터 프로필 필드를 채워주세요.")
        return

    st.session_state.character_profile = {
        "Profile": profile,
        "Story": story,
        "Goals & Pains": goals_pains,
        "Behavior": behavior,
        "Motivation": motivation
    }

    image_prompt = f"Imagine a character based on the following description: Profile: {profile}, Story: {story}, Goals & Pains: {goals_pains}, Behavior: {behavior}, Motivation: {motivation}. Generate a vibrant, detailed, and visually appealing image of this character."
    
    generated_image_url = generate_image(image_prompt)
    if generated_image_url:
        st.session_state.character_image_url = generated_image_url
    else:
        st.session_state.character_image_url = None

    persona_prompt = (
        f"당신은 이제 다음 페르소나를 가진 캐릭터입니다:\n\n"
        f"**[프로필]**\n{profile}\n\n"
        f"**[스토리]**\n{story}\n\n"
        f"**[목표 및 어려움]**\n{goals_pains}\n\n"
        f"**[행동]**\n{behavior}\n\n"
        f"**[동기]**\n{motivation}\n\n"
        f"이 캐릭터의 성격과 배경에 완벽하게 맞춰서 사용자에게 답변하세요. "
        f"사용자의 질문에 대해 이 캐릭터라면 어떻게 반응하고 말할지 상상하여 자연스럽게 대화하세요. "
        f"답변은 한국어로 해주세요."
    )

    st.session_state.chat_session = CHAT_MODEL.start_chat(
        history=[
            {"role": "user", "parts": [persona_prompt]},
            {"role": "model", "parts": ["네, 알겠습니다. 이제 이 페르소나를 기반으로 대화를 시작하겠습니다!"]}
        ]
    )
    st.session_state.chat_history = [
        {"role": "model", "parts": ["안녕하세요! 어떤 캐릭터를 만들고 싶으신가요? 위 양식을 채워주세요."]},
        {"role": "model", "parts": ["네, 알겠습니다. 이제 이 페르소나를 기반으로 대화를 시작하겠습니다!"]}
    ]
    st.session_state.character_ready = True
    st.success("🎉 캐릭터가 생성되었고, 대화를 시작할 준비가 되었습니다!")

st.title("🤖 페르소나 메이커 챗봇")
st.markdown("---")

with st.expander("📝 캐릭터 프로필 입력", expanded=not st.session_state.character_ready):
    st.write("새로운 캐릭터의 페르소나를 정의해주세요. 입력된 정보에 따라 캐릭터의 성격과 대화 방식이 결정됩니다.")
    st.text_area(
        "**Profile (프로필):** 캐릭터의 이름, 나이, 직업, 특징 등 기본적인 정보를 입력하세요.",
        height=100,
        key="input_profile",
        value=st.session_state.character_profile.get("Profile", "")
    )
    st.text_area(
        "**Story (스토리):** 캐릭터의 배경 스토리, 과거 경험, 성장 과정 등을 자세히 작성해주세요.",
        height=150,
        key="input_story",
        value=st.session_state.character_profile.get("Story", "")
    )
    st.text_area(
        "**Goals & Pains (목표 및 어려움):** 캐릭터가 추구하는 목표, 그리고 그 과정에서 겪는 어려움이나 고민을 설명하세요.",
        height=150,
        key="input_goals_pains",
        value=st.session_state.character_profile.get("Goals & Pains", "")
    )
    st.text_area(
        "**Behavior (행동):** 캐릭터의 일반적인 행동 방식, 습관, 대화 스타일 등을 구체적으로 기술하세요.",
        height=150,
        key="input_behavior",
        value=st.session_state.character_profile.get("Behavior", "")
    )
    st.text_area(
        "**Motivation (동기):** 캐릭터가 특정 행동을 하는 근본적인 이유, 신념, 가치관 등을 설명하세요.",
        height=150,
        key="input_motivation",
        value=st.session_state.character_profile.get("Motivation", "")
    )

    st.button("✅ 캐릭터 생성 및 대화 시작", on_click=create_character_and_chat_session, type="primary")

st.markdown("---")

if st.session_state.character_ready:
    st.subheader("👥 현재 캐릭터 정보")
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.session_state.character_image_url:
            st.image(st.session_state.character_image_url, caption="생성된 캐릭터 이미지", use_container_width=True)
        else:
            st.warning("캐릭터 이미지를 불러올 수 없습니다.")
    with col2:
        for key, value in st.session_state.character_profile.items():
            st.markdown(f"**{key}:** {value}")
    st.markdown("---")

if st.session_state.character_ready and st.session_state.chat_session:
    st.subheader("💬 캐릭터와 대화하기")

    for message in st.session_state.chat_history:
        if message["parts"][0] != "네, 알겠습니다. 이제 이 페르소나를 기반으로 대화를 시작하겠습니다!":
            with st.chat_message(message["role"], avatar=_chat_avatar_for_role(message["role"])):
                st.markdown(message["parts"][0])

    user_query = st.chat_input("캐릭터에게 메시지를 보내세요...", key="chat_input")
    if user_query:
        st.session_state.chat_history.append({"role": "user", "parts": [user_query]})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.spinner("생각 중..."):
            try:
                response = st.session_state.chat_session.send_message(user_query)
                model_response = response.text
                st.session_state.chat_history.append({"role": "model", "parts": [model_response]})
                with st.chat_message("model", avatar=_chat_avatar_for_role("model")):
                    st.markdown(model_response)
            except Exception as e:
                st.error(f"챗봇 응답 생성 중 오류 발생: {e}")
                st.session_state.chat_history.append({"role": "model", "parts": ["죄송합니다. 오류가 발생하여 응답을 드릴 수 없습니다."]})
                with st.chat_message("model"):
                    st.markdown("죄송합니다. 오류가 발생하여 응답을 드릴 수 없습니다.")
else:
    st.info("⬆️ 먼저 캐릭터 프로필을 입력하고 '캐릭터 생성 및 대화 시작' 버튼을 눌러주세요.")

st.markdown("---")
st.caption("powered by Google Gemini API & Streamlit")
# --- 여기까지 업데이트된 코드 끝 ---
