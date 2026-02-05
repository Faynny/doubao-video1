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
# 2. 🔐 访问密码设置
# ==========================================
APP_PASSWORD = "123456"  # <--- 在这里修改你的密码

# --- 登录拦截逻辑 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.password_input == APP_PASSWORD:
        st.session_state.authenticated = True
        del st.session_state.password_input
    else:
        st.error("❌ 密码错误")

if not st.session_state.authenticated:
    st.markdown("### 🔒 系统锁定")
    st.text_input("请输入访问密码：", type="password", on_change=check_password, key="password_input")
    st.stop() 

# ==========================================
# 3. 初始化全局状态
# ==========================================
if "history" not in st.session_state:
    st.session_state.history = []

# --- CSS 美化 ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div.stButton > button:first-child {
        background-color: #FF4B4B; color: white; border-radius: 8px;
        height: 45px; font-size: 18px; font-weight: bold; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #FF2B2B; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 核心功能函数
# ==========================================

# --- 上传图片到 tmpfiles.org 获取直链 ---
def upload_to_temp_host(uploaded_file):
    try:
        url = 'https://tmpfiles.org/api/v1/upload'
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(url, files=files)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return None
    except Exception as e:
        st.error(f"图床连接失败: {e}")
        return None

# --- 带相册功能的图片输入组件 (支持保留10张) ---
def handle_image_input(label, key_prefix):
    st.markdown(f"**{label}**")
    
    # 初始化相册 Session
    gallery_key = f"gallery_{key_prefix}"
    if gallery_key not in st.session_state:
        st.session_state[gallery_key] = []

    tab1, tab2 = st.tabs(["🖼️ 图片库 (多张)", "🔗 粘贴链接"])

    # === Tab 1: 相册模式 ===
    with tab1:
        # 上传区
        uploaded_files = st.file_uploader(
            f"上传新图片 (自动存入下方相册)", 
            type=["jpg", "png", "jpeg"], 
            accept_multiple_files=True,
            key=f"uploader_{key_prefix}"
        )
        
        # 将新文件加入相册
        if uploaded_files:
            for new_file in uploaded_files:
                if len(st.session_state[gallery_key]) < 10:
                    # 简单去重 (按文件名)
                    current_names = [f.name for f in st.session_state[gallery_key]]
                    if new_file.name not in current_names:
                        st.session_state[gallery_key].append(new_file)
        
        # 显示选择区
        if len(st.session_state[gallery_key]) > 0:
            st.divider()
            st.caption(f"📚 已存 {len(st.session_state[gallery_key])}/10 张 (刷新不丢失)")
            
            # 选项列表
            options = [f"{i+1}. {f.name}" for i, f in enumerate(st.session_state[gallery_key])]
            selected_option = st.radio("请选择一张：", options, horizontal=True, key=f"radio_{key_prefix}")
            
            # 清空按钮
            if st.button(f"🗑️ 清空相册", key=f"clear_{key_prefix}"):
                st.session_state[gallery_key] = []
                st.rerun()

            # 返回选中的文件
            if selected_option:
                index = options.index(selected_option)
                selected_file = st.session_state[gallery_key][index]
                st.image(selected_file, caption="✅ 当前选中", width=200)
                return selected_file, "file"
        else:
            st.info("👈 请上传图片，暂存后可重复使用。")

    # === Tab 2: URL 模式 ===
    image_url = None
    with tab2:
        url_input = st.text_input(f"URL", key=f"url_{key_prefix}", placeholder="https://...")
        if url_input: image_url = url_input
    
    if image_url:
        st.image(image_url, width=200)
        return image_url, "url"
    
    return None, None

# ==========================================
# 5. 侧边栏与主界面
# ==========================================
with st.sidebar:
    st.header("⚙️ 参数配置")
    secret_key = st.secrets.get("ARK_API_KEY", None)
    env_key = os.environ.get("ARK_API_KEY", "")
    default_key = secret_key if secret_key else env_key
    
    api_key = st.text_input("API Key", value=default_key, type="password")
    
    st.divider()
    model_id = st.text_input("模型 ID", value="doubao-seedance-1-5-pro-251215")
    resolution = st.selectbox("清晰度", ["720p", "1080p"], index=0)
    ratio = st.selectbox("视频比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长 (秒)", 2, 10, 5)
    
    st.divider()
    st.markdown("### ☁️ 云端同步")
    if st.button("🔄 同步云端历史记录"):
        if not api_key:
            st.error("需要 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在连接..."):
                    resp = client.content_generation.tasks.list(page_size=10, status="succeeded")
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            if not any(h.get('task_id') == item.id for h in st.session_state.history):
                                st.session_state.history.append({
                                    "task_id": item.id,
                                    "time": "云端记录",
                                    "prompt": "☁️ 云端同步任务",
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        st.success(f"同步了 {count} 条记录")
            except Exception as e:
                st.error(str(e))

st.title("🎬 豆包视频生成 Pro")
col1, col2 = st.columns([1.2, 1])

with col1:
    prompt_text = st.text_area("提示词", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=140)
    st.info("🖼️ **首帧图片 (必填)**")
    first_frame_data, first_frame_type = handle_image_input("选择首帧", "first")

with col2:
    st.write("") 
    st.write("") 
    st.success("🏁 **尾帧图片 (可选)**")
    last_frame_data, last_frame_type = handle_image_input("选择尾帧", "last")

st.divider()

# ==========================================
# 6. 生成逻辑
# ==========================================
if st.button("🚀 立即生成视频"):
    if not api_key: st.error("❌ 请输入 API Key"); st.stop()
    if not first_frame_data: st.error("❌ 必须有首帧图片"); st.stop()

    status_container = st.status("🚀 任务启动...", expanded=True)
    
    try:
        final_first_url = first_frame_data
        final_last_url = last_frame_data

        if first_frame_type == "file":
            status_container.write("📤 上传首帧...")
            final_first_url = upload_to_temp_host(first_frame_data)
            if not final_first_url: status_container.update(label="❌ 上传失败", state="error"); st.stop()

        if last_frame_type == "file" and last_frame_data:
            status_container.write("📤 上传尾帧...")
            final_last_url = upload_to_temp_host(last_frame_data)
            if not final_last_url: status_container.update(label="❌ 上传失败", state="error"); st.stop()

        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        
        content_payload = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": final_first_url}, "role": "first_frame"}
        ]
        if final_last_url:
            content_payload.append({"type": "image_url", "image_url": {"url": final_last_url}, "role": "last_frame"})

        status_container.write("🤖 正在生成...")
        create_result = client.content_generation.tasks.create(
            model=model_id,
            content=content_payload,
            generate_audio=True,
            ratio=ratio,
            resolution=resolution,
            duration=duration,
        )
        task_id = create_result.id
        
        start_time = time.time()
        while True:
            if time.time() - start_time > 600: status_container.update(label="❌ 超时", state="error"); break
            get_result = client.content_generation.tasks.get(task_id=task_id)
            if get_result.status == "succeeded":
                video_url = get_result.content.video_url
                status_container.update(label="✅ 成功！", state="complete", expanded=False)
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
            elif get_result.status == "failed":
                status_container.update(label="❌ 失败", state="error"); st.error(get_result.error); break
            else:
                time.sleep(3)
    except Exception as e:
        status_container.update(label="❌ 异常", state="error")
        st.error(str(e))

# ==========================================
# 7. 历史记录
# ==========================================
if len(st.session_state.history) > 0:
    st.divider()
    st.subheader(f"📜 历史记录 ({len(st.session_state.history)})")
    for item in reversed(st.session_state.history):
        with st.expander(f"🕒 {item['time']} - {item.get('task_id', '')}", expanded=True):
            h1, h2 = st.columns([1, 1.5])
            h1.video(item['video_url'])
            h2.info(f"提示词: {item['prompt']}")
            h2.markdown(f"[📥 下载视频]({item['video_url']})")
