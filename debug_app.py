import streamlit as st
import subprocess

st.set_page_config(layout="wide")
st.title("🕵️‍♂️ Streamlit 환경 진단 앱")
st.warning("이 페이지의 스크린샷을 전체 화면으로 찍어서 공유해주세요.")

# --- 1. st.secrets 내용 확인 ---
st.header("1. 앱이 인식하는 `secrets.toml` 내용")
st.info("이곳에 출력된 'connections' -> 'gsheets' 안에 'type' 필드가 있는지 반드시 확인해주세요. 없어야 정상입니다.")
try:
    # to_dict()를 사용해 secrets 객체를 안전하게 딕셔너리로 변환
    secrets_dict = st.secrets.to_dict()
    st.json(secrets_dict)
except Exception as e:
    st.error(f"st.secrets를 읽는 중 오류 발생: {e}")

# --- 2. 설치된 라이브러리 목록 확인 ---
st.header("2. 실제 설치된 라이브러리 목록")
st.info("'st-gsheets-connection'이 이 목록에 있는지, 버전은 무엇인지 확인해주세요.")
try:
    # pip freeze 명령 실행
    result = subprocess.run(['pip', 'freeze'], capture_output=True, text=True, check=True)
    st.text(result.stdout)
except Exception as e:
    st.error(f"라이브러리 목록을 가져오는 중 오류 발생: {e}")

# --- 3. Google Sheets 연결 직접 시도 ---
st.header("3. 실제 `st.connection('gsheets')` 호출 결과")
st.info("이곳에서 발생하는 실제 오류 메시지를 확인합니다.")
try:
    # 문제의 코드를 직접 실행
    conn = st.connection("gsheets")
    
    st.success("✅ Google Sheets 연결에 성공했습니다!")
    st.balloons()
    
    # 성공 시, 간단한 데이터 읽기 시도
    st.write("연결 성공 후, 간단한 데이터 읽기를 시도합니다...")
    # '시트1'은 실제 사용하는 시트 이름으로 바꾸거나, 첫 번째 시트를 읽도록 그대로 두세요.
    df = conn.read(worksheet="시트1") 
    st.dataframe(df)

except Exception as e:
    st.error("연결 시도 중 오류가 발생했습니다. 아래는 전체 오류 메시지입니다.")
    # st.exception()은 오류의 전체 Traceback을 깔끔하게 보여줍니다.
    st.exception(e)