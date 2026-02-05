import streamlit as st
import os
import time
import requests
from datetime import datetime
from volcenginesdkarkruntime import Ark

# --- 1. UI 配置 ---
st.set_page_config(page_title="豆包视频生成 Pro", page_icon="🎬", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []

# --- CSS 美化 ---
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div.stButton > button:first-child {
        background-color: #FF4B4B; color: white; border-radius: 10px;
        height: 50px; font-size: 18px; font-weight: bold; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #FF2B2B; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 辅助函数 ---
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
    except: return None

def handle_image_input(label, key_prefix):
    st.markdown(f"### {label}")
    tab1, tab2 = st.tabs(["🔗 粘贴链接", "📤 上传图片"])
    image_url = None
    with tab1:
        url_input = st.text_input(f"请输入图片 URL", key=f"url_{key_prefix}")
        if url_input: image_url = url_input
    with tab2:
        file_input = st.file_uploader(f"选择本地文件", type=["jpg", "png"], key=f"file_{key_prefix}")
        if file_input:
            st.image(file_input, width=150)
            return file_input, "file"
    if image_url:
        st.image(image_url, width=150)
        return image_url, "url"
    return None, None

# --- 侧边栏配置 ---
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
    st.markdown("### ☁️ 历史记录管理")
    
    # === 🆕 新增功能：同步云端列表 ===
    if st.button("🔄 同步最近10条云端记录"):
        if not api_key:
            st.error("需要 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在从云端拉取数据..."):
                    # 调用 list 接口
                    resp = client.content_generation.tasks.list(page_size=10, status="succeeded")
                    
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            # 防止重复添加 (根据 task_id 判断)
                            task_id = item.id
                            exists = any(h['task_id'] == task_id for h in st.session_state.history)
                            
                            if not exists:
                                # 尝试获取提示词，如果获取不到则显示默认文本
                                # 注意：List 接口返回的结构可能不包含完整的 prompt 文本，视具体 API 版本而定
                                # 这里做了一个防御性编程
                                try:
                                    # 尝试从 request 参数里找 prompt，如果找不到就写"云端同步视频"
                                    prompt_display = "☁️ 云端同步记录" 
                                    # 如果 future API 更新支持返回 content，可以这里解析
                                except:
                                    prompt_display = "☁️ 云端同步记录"

                                st.session_state.history.append({
                                    "task_id": task_id,
                                    "time": datetime.fromtimestamp(item.created_at).strftime("%m-%d %H:%M") if hasattr(item, 'created_at') else "未知时间",
                                    "prompt": prompt_display, 
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        st.success(f"成功同步 {count} 条新记录！")
                    else:
                        st.warning("未找到记录")
            except Exception as e:
                st.error(f"同步失败: {str(e)}")

# --- 主界面 ---
st.title("🎬 豆包视频生成 Pro")
st.caption("支持图片上传 | 自定义分辨率 | 云端历史回溯")

col1, col2 = st.columns([1.2, 1])
with col1:
    prompt_text = st.text_area("提示词", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=150)
    first_frame_data, first_frame_type = handle_image_input("首帧图片 (必填)", "first")
with col2:
    st.write("")
    st.write("")
    last_frame_data, last_frame_type = handle_image_input("尾帧图片 (可选)", "last")

st.divider()

if st.button("🚀 立即生成视频"):
    if not api_key or not first_frame_data:
        st.error("请检查 API Key 和首帧图片")
        st.stop()

    status_container = st.status("🚀 任务初始化中...", expanded=True)
    
    try:
        final_first_url = first_frame_data
        final_last_url = last_frame_data
        if first_frame_type == "file": final_first_url = upload_to_temp_host(first_frame_data)
        if last_frame_type == "file" and last_frame_data: final_last_url = upload_to_temp_host(last_frame_data)
        
        if not final_first_url: st.stop()

        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        content_payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": final_first_url}, "role": "first_frame"}]
        if final_last_url: content_payload.append({"type": "image_url", "image_url": {"url": final_last_url}, "role": "last_frame"})

        status_container.write(f"🤖 正在生成 ({resolution})...")
        create_result = client.content_generation.tasks.create(
            model=model_id, content=content_payload, generate_audio=True,
            ratio=ratio, resolution=resolution, duration=duration
        )
        task_id = create_result.id
        
        start_time = time.time()
        while True:
            if time.time() - start_time > 600: break
            get_result = client.content_generation.tasks.get(task_id=task_id)
            if get_result.status == "succeeded":
                video_url = get_result.content.video_url
                status_container.update(label="✅ 成功！", state="complete", expanded=False)
                
                # 保存到历史
                st.session_state.history.append({
                    "task_id": task_id,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "prompt": prompt_text,
                    "video_url": video_url,
                    "model": model_id
                })
                st.video(video_url)
                break
            elif get_result.status == "failed":
                status_container.update(label="❌ 失败", state="error"); break
            else: time.sleep(3)
    except Exception as e: st.error(str(e))

# --- 历史记录展示区 ---
if len(st.session_state.history) > 0:
    st.divider()
    st.subheader("📜 视频列表 (本地+云端)")
    
    # 倒序显示
    for item in reversed(st.session_state.history):
        with st.expander(f"🕒 {item['time']} - {item.get('task_id', 'Unknown')}", expanded=True):
            cols = st.columns([1, 1.5])
            with cols[0]:
                st.video(item['video_url'])
            with cols[1]:
                st.info(f"**提示词:** {item['prompt']}")
                st.text(f"ID: {item.get('task_id')}")
                st.markdown(f"[📥 下载链接]({item['video_url']})")
