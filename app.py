import streamlit as st
import os
import time
import requests
from volcenginesdkarkruntime import Ark

# --- 1. UI 配置 (必须放在代码最开头) ---
st.set_page_config(
    page_title="豆包视频生成 Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 自定义 CSS (隐藏水印，美化按钮) ---
st.markdown("""
<style>
    /* 隐藏右上角汉堡菜单和底部 Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /*以此美化主按钮 */
    div.stButton > button:first-child {
        background-color: #FF4B4B;
        color: white;
        border-radius: 10px;
        height: 50px;
        font-size: 20px;
        font-weight: bold;
        width: 100%;
        border: none;
    }
    div.stButton > button:hover {
        background-color: #FF2B2B;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 核心功能函数 ---

def upload_to_temp_host(uploaded_file):
    """
    修复版：使用 tmpfiles.org 上传图片
    """
    try:
        url = 'https://tmpfiles.org/api/v1/upload'
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(url, files=files)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                original_url = data['data']['url']
                # 替换为直链地址
                return original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return None
    except Exception as e:
        st.error(f"图片上传失败: {e}")
        return None

def handle_image_input(label, key_prefix):
    st.markdown(f"### {label}")
    tab1, tab2 = st.tabs(["🔗 粘贴链接", "📤 上传图片"])
    
    image_url = None
    with tab1:
        url_input = st.text_input(f"请输入图片 URL", key=f"url_{key_prefix}")
        if url_input:
            image_url = url_input
    with tab2:
        file_input = st.file_uploader(f"选择本地文件", type=["jpg", "png"], key=f"file_{key_prefix}")
        if file_input:
            st.image(file_input, width=150)
            return file_input, "file"
            
    if image_url:
        st.image(image_url, width=150)
        return image_url, "url"
    
    return None, None

# --- 4. 页面主结构 ---

st.title("🎬 豆包视频生成器")
st.markdown("##### 🚀 基于 Volcengine Ark | AI Video Generation")
st.divider()

# 侧边栏
with st.sidebar:
    st.header("⚙️ 参数配置")
    
    # 获取 API Key (优先读 Secrets，没有则读输入框)
    secret_key = st.secrets.get("ARK_API_KEY", None)
    env_key = os.environ.get("ARK_API_KEY", "")
    default_key = secret_key if secret_key else env_key
    
    api_key = st.text_input("API Key", value=default_key, type="password", help="请在 Streamlit Secrets 中配置以隐藏")
    
    st.write("---")
    model_id = st.text_input("模型 ID", value="doubao-seedance-1-5-pro-251215")
    ratio = st.selectbox("视频比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("视频时长 (秒)", 2, 10, 5)
    
    st.info("💡 提示：更长的视频生成时间会更久")

# 主内容区：使用两列布局
col1, col2 = st.columns([1.2, 1])

with col1:
    st.success("📝 **第一步：输入提示词**")
    prompt_text = st.text_area("描述你想要的视频画面", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=150)
    
    st.warning("🖼️ **第二步：上传图片**")
    # 首帧
    first_frame_data, first_frame_type = handle_image_input("首帧图片 (必填)", "first")
    
with col2:
    st.markdown("<br><br>", unsafe_allow_html=True) # 占位符，为了对齐
    # 尾帧
    last_frame_data, last_frame_type = handle_image_input("尾帧图片 (可选)", "last")

st.divider()

# --- 5. 执行逻辑 ---
if st.button("🚀 立即生成视频"):
    if not api_key:
        st.error("❌ 未检测到 API Key，请在侧边栏输入或配置 Secrets")
        st.stop()
        
    if not first_frame_data:
        st.error("❌ 请务必上传或输入首帧图片")
        st.stop()

    # 漂亮的进度显示组件
    status_container = st.status("🚀 任务初始化中...", expanded=True)
    
    try:
        # 上传逻辑
        final_first_url = first_frame_data
        final
