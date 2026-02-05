import streamlit as st
import os
import time
import requests
from datetime import datetime
from volcenginesdkarkruntime import Ark

# ==========================================
# 1. 页面基础配置 (必须放在第一行)
# ==========================================
st.set_page_config(
    page_title="豆包视频生成 Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 🔐 访问密码设置 (请在这里修改密码!)
# ==========================================
APP_PASSWORD = "HYMS"  # <--- 请修改这里，设置你的专属密码

# --- 登录拦截逻辑 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.password_input == APP_PASSWORD:
        st.session_state.authenticated = True
        del st.session_state.password_input
    else:
        st.error("❌ 密码错误，请重试")

if not st.session_state.authenticated:
    st.markdown("""
    <style>
        .stTextInput > div > div > input {text-align: center; font-size: 20px;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### 🔒 系统锁定")
    st.markdown("请输入访问密码以继续：")
    st.text_input("Password", type="password", on_change=check_password, key="password_input")
    st.stop() # ⛔️ 密码不对，停止加载下方代码

# ==========================================
# 3. 程序主逻辑开始
# ==========================================

# 初始化历史记录
if "history" not in st.session_state:
    st.session_state.history = []

# --- CSS 美化 ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* 按钮样式优化 */
    div.stButton > button:first-child {
        background-color: #FF4B4B; color: white; border-radius: 8px;
        height: 45px; font-size: 18px; font-weight: bold; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #FF2B2B; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 辅助函数：上传本地图片到临时图床 ---
def upload_to_temp_host(uploaded_file):
    """上传图片到 tmpfiles.org 并获取直链"""
    try:
        url = 'https://tmpfiles.org/api/v1/upload'
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(url, files=files)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                # 必须替换路径才能获取直链
                return data['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return None
    except Exception as e:
        st.error(f"图床连接失败: {e}")
        return None

# --- 辅助函数：图片输入组件 ---
def handle_image_input(label, key_prefix):
    st.markdown(f"**{label}**")
    tab1, tab2 = st.tabs(["🔗 粘贴链接", "📤 上传图片"])
    image_url = None
    with tab1:
        url_input = st.text_input(f"URL ({key_prefix})", key=f"url_{key_prefix}", placeholder="https://...")
        if url_input: image_url = url_input
    with tab2:
        file_input = st.file_uploader(f"File ({key_prefix})", type=["jpg", "png", "jpeg"], key=f"file_{key_prefix}")
        if file_input:
            st.image(file_input, width=150)
            return file_input, "file"
    if image_url:
        st.image(image_url, width=150)
        return image_url, "url"
    return None, None

# ==========================================
# 4. 侧边栏配置
# ==========================================
with st.sidebar:
    st.header("⚙️ 参数配置")
    
    # 获取 API Key (优先读 Secrets，其次读环境变量)
    secret_key = st.secrets.get("ARK_API_KEY", None)
    env_key = os.environ.get("ARK_API_KEY", "")
    default_key = secret_key if secret_key else env_key
    
    api_key = st.text_input("API Key", value=default_key, type="password", help="请输入火山引擎 Ark API Key")
    
    st.divider()
    model_id = st.text_input("模型 ID", value="doubao-seedance-1-5-pro-251215")
    resolution = st.selectbox("清晰度 (Resolution)", ["720p", "1080p"], index=0)
    ratio = st.selectbox("视频比例 (Ratio)", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长 (Duration)", 2, 10, 5)
    
    st.divider()
    st.markdown("### ☁️ 云端同步")
    if st.button("🔄 同步最近10条历史记录"):
        if not api_key:
            st.error("请先输入 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在连接火山引擎服务器..."):
                    resp = client.content_generation.tasks.list(page_size=10, status="succeeded")
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            # 避免重复添加
                            if not any(h.get('task_id') == item.id for h in st.session_state.history):
                                st.session_state.history.append({
                                    "task_id": item.id,
                                    "time": datetime.fromtimestamp(item.created_at).strftime("%m-%d %H:%M") if hasattr(item, 'created_at') else "云端记录",
                                    "prompt": "☁️ 云端同步任务",
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        st.success(f"同步完成，新增 {count} 条记录！")
                    else:
                        st.warning("云端没有找到最近的成功记录。")
            except Exception as e:
                st.error(f"同步失败: {str(e)}")

# ==========================================
# 5. 主界面布局
# ==========================================
st.title("🎬 Seedance 1.5Pro")
st.caption("🚀 Powered by Volcengine Ark | 安全加密版")

col1, col2 = st.columns([1.2, 1])

with col1:
    st.info("📝 **Prompt 设置**")
    prompt_text = st.text_area("提示词", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=140)
    
    st.warning("🖼️ **首帧图片 (必须)**")
    first_frame_data, first_frame_type = handle_image_input("选择首帧", "first")

with col2:
    st.write("") # 占位
    st.write("") 
    st.success("🏁 **尾帧图片 (可选)**")
    last_frame_data, last_frame_type = handle_image_input("选择尾帧", "last")

st.divider()

# ==========================================
# 6. 生成核心逻辑
# ==========================================
if st.button("🚀 立即生成视频 (Generate)"):
    # 基础检查
    if not api_key:
        st.error("❌ 错误: API Key 为空，请在侧边栏填写。")
        st.stop()
    if not first_frame_data:
        st.error("❌ 错误: 必须提供首帧图片。")
        st.stop()

    status_container = st.status("🚀 任务启动中...", expanded=True)
    
    try:
        # 1. 处理图片上传
        final_first_url = first_frame_data
        final_last_url = last_frame_data

        if first_frame_type == "file":
            status_container.write("📤 正在上传首帧图片到中转服务器...")
            final_first_url = upload_to_temp_host(first_frame_data)
            if not final_first_url:
                status_container.update(label="❌ 首帧上传失败", state="error"); st.stop()

        if last_frame_type == "file" and last_frame_data:
            status_container.write("📤 正在上传尾帧图片到中转服务器...")
            final_last_url = upload_to_temp_host(last_frame_data)
            if not final_last_url:
                status_container.update(label="❌ 尾帧上传失败", state="error"); st.stop()

        # 2. 构建 API 请求
        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        
        content_payload = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": final_first_url}, "role": "first_frame"}
        ]
        if final_last_url:
            content_payload.append(
                {"type": "image_url", "image_url": {"url": final_last_url}, "role": "last_frame"}
            )

        status_container.write(f"🤖 提交任务... (清晰度: {resolution}, 比例: {ratio})")
        
        create_result = client.content_generation.tasks.create(
            model=model_id,
            content=content_payload,
            generate_audio=True,
            ratio=ratio,
            resolution=resolution,
            duration=duration,
        )
        task_id = create_result.id
        status_container.write(f"🆔 任务 ID: `{task_id}` - 正在排队生成...")

        # 3. 轮询状态
        start_time = time.time()
        while True:
            # 10分钟超时保护
            if time.time() - start_time > 600:
                status_container.update(label="❌ 生成超时", state="error")
                break

            get_result = client.content_generation.tasks.get(task_id=task_id)
            status = get_result.status
            
            if status == "succeeded":
                video_url = get_result.content.video_url
                status_container.update(label="✅ 生成成功！", state="complete", expanded=False)
                
                # 存入历史
                st.session_state.history.append({
                    "task_id": task_id,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "prompt": prompt_text,
                    "video_url": video_url,
                    "model": model_id
                })
                
                st.balloons()
                st.video(video_url)
                break
            elif status == "failed":
                status_container.update(label="❌ 生成失败", state="error")
                st.error(f"API Error: {get_result.error}")
                break
            else:
                time.sleep(3) # 等待3秒再查

    except Exception as e:
        status_container.update(label="❌ 系统异常", state="error")
        st.error(f"Error Details: {str(e)}")

# ==========================================
# 7. 历史记录展示区
# ==========================================
if len(st.session_state.history) > 0:
    st.divider()
    st.subheader(f"📜 历史记录 (共 {len(st.session_state.history)} 条)")
    
    # 倒序遍历，最新的显示在最上面
    for item in reversed(st.session_state.history):
        with st.expander(f"🕒 {item['time']} - {item.get('task_id', 'Task')}", expanded=True):
            h_col1, h_col2 = st.columns([1, 1.5])
            with h_col1:
                st.video(item['video_url'])
            with h_col2:
                st.info(f"**提示词:** {item['prompt']}")
                st.text(f"Model: {item.get('model')}")
                st.markdown(f"[📥 点击下载视频]({item['video_url']})")
