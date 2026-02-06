import streamlit as st
import os
import time
import requests
import json
from datetime import datetime
from volcenginesdkarkruntime import Ark

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(
    page_title="豆包视频生成 Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_PASSWORD = "HYMS"  # <--- 你的密码
DB_FILE = "local_prompts.json" # 我们的“小账本”文件

# --- 登录逻辑 ---
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
# 2. 本地数据库管理 (核心新增功能)
# ==========================================
def load_local_db():
    """读取本地小账本"""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_to_local_db(task_id, prompt):
    """把 ID 和提示词记在账本上"""
    db = load_local_db()
    db[task_id] = prompt
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存失败: {e}")

# ==========================================
# 3. 初始化与辅助函数
# ==========================================
if "history" not in st.session_state:
    st.session_state.history = []

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div.stButton > button:first-child {
        background-color: #FF4B4B; color: white; border-radius: 8px;
        height: 45px; font-size: 18px; font-weight: bold; width: 100%; border: none;
    }
    div.stButton > button:hover { background-color: #FF2B2B; color: white; }
    div[data-testid="column"] button[kind="secondary"] { background-color: #6c757d; }
    div[data-testid="stVerticalBlockBorderWrapper"] { padding: 10px; }
</style>
""", unsafe_allow_html=True)

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

# --- 智能提取函数 (结合本地账本) ---
def get_prompt_intelligent(item):
    """
    先查本地账本，如果没有，再尝试从 API 提取，最后兜底。
    """
    task_id = item.id
    
    # 1. 优先查本地数据库 (最准确)
    local_db = load_local_db()
    if task_id in local_db:
        return "📝 " + local_db[task_id] # 加个图标表示是本地找回的
    
    # 2. 尝试从 API 结构里找 (虽然通常没有)
    try:
        if hasattr(item, 'content') and isinstance(item.content, list):
            for c in item.content:
                if hasattr(c, 'type') and c.type == 'text':
                    return getattr(c, 'text', '')
                if isinstance(c, dict) and c.get('type') == 'text':
                    return c.get('text', '')
    except: pass
    
    # 3. 如果都没有，返回基本信息兜底
    meta = []
    if hasattr(item, 'resolution'): meta.append(str(item.resolution))
    if hasattr(item, 'duration'): meta.append(f"{item.duration}s")
    return f"☁️ 云端任务 ({' | '.join(meta)}) - 无提示词记录"

def handle_image_input(label, key_prefix):
    st.markdown(f"**{label}**")
    gallery_key = f"gallery_{key_prefix}"
    if gallery_key not in st.session_state: st.session_state[gallery_key] = []

    tab1, tab2 = st.tabs(["🖼️ 图片库", "🔗 URL"])
    with tab1:
        ups = st.file_uploader(f"上传 ({key_prefix})", type=["jpg","png"], accept_multiple_files=True, key=f"u_{key_prefix}")
        if ups:
            for f in ups:
                if len(st.session_state[gallery_key]) < 10:
                    if f.name not in [x.name for x in st.session_state[gallery_key]]:
                        st.session_state[gallery_key].append(f)
        
        if st.session_state[gallery_key]:
            with st.expander(f"👁️ 预览 ({len(st.session_state[gallery_key])}张)", expanded=False):
                cols = st.columns(5)
                for i, img_file in enumerate(st.session_state[gallery_key]):
                    with cols[i % 5]:
                        st.image(img_file, caption=f"{i+1}", use_container_width=True)

            options = [f"{i+1}. {f.name}" for i, f in enumerate(st.session_state[gallery_key])]
            sel = st.radio("选择:", options, horizontal=True, key=f"r_{key_prefix}", index=None)
            
            b_col1, b_col2 = st.columns([1, 1])
            if b_col1.button("🗑️ 清空", key=f"c_{key_prefix}"):
                st.session_state[gallery_key] = []
                st.rerun()
            b_col2.button("❌ 取消", key=f"d_{key_prefix}", on_click=lambda: st.session_state.update({f"r_{key_prefix}": None}))
                
            if sel: 
                selected_file = st.session_state[gallery_key][options.index(sel)]
                st.image(selected_file, caption="✅ 选中", width=250)
                return selected_file, "file"
    with tab2:
        url = st.text_input("URL", key=f"url_{key_prefix}")
        if url: return url, "url"
    return None, None

# ==========================================
# 4. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 配置")
    api_key = st.text_input("API Key", value=st.secrets.get("ARK_API_KEY", os.environ.get("ARK_API_KEY", "")), type="password")
    
    st.divider()
    model_id = st.text_input("模型ID", value="doubao-seedance-1-5-pro-251215")
    resolution = st.selectbox("清晰度", ["720p", "1080p"])
    ratio = st.selectbox("比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长", 2, 10, 5)
    
    st.divider()
    if st.button("🔄 同步最近 50 条"):
        if not api_key:
            st.error("缺 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在拉取数据并匹配本地账本..."):
                    resp = client.content_generation.tasks.list(page_size=50, status="succeeded")
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            if not any(h.get('task_id') == item.id for h in st.session_state.history):
                                
                                # === 调用智能提取 (查本地库) ===
                                prompt_str = get_prompt_intelligent(item)
                                # ===========================
                                
                                created_ts = getattr(item, 'created_at', 0)
                                st.session_state.history.append({
                                    "task_id": item.id,
                                    "created_at": created_ts,
                                    "time": datetime.fromtimestamp(created_ts).strftime("%m-%d %H:%M"),
                                    "prompt": prompt_str,
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        st.session_state.history.sort(key=lambda x: x['created_at'], reverse=True)
                        st.success(f"同步成功！匹配本地记录 {count} 条")
                    else: st.warning("无数据")
            except Exception as e: st.error(str(e))

# ==========================================
# 5. 主界面
# ==========================================
st.title("🎬 豆包视频生成 Pro")
c1, c2 = st.columns([1.2, 1])
with c1:
    prompt_text = st.text_area("提示词", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=140)
    first_data, first_type = handle_image_input("首帧 (必填)", "f")
with c2:
    st.write(""); st.write("")
    last_data, last_type = handle_image_input("尾帧 (可选)", "l")

st.divider()

if st.button("🚀 生成视频"):
    if not api_key or not first_data: st.error("检查 Key 和图片"); st.stop()
    
    status = st.status("🚀 启动中...", expanded=True)
    try:
        f_url = upload_to_temp_host(first_data) if first_type == "file" else first_data
        l_url = None
        if last_type == "file" and last_data: l_url = upload_to_temp_host(last_data)
        elif last_data: l_url = last_data
        
        if not f_url: status.update(label="上传失败", state="error"); st.stop()

        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": f_url}, "role": "first_frame"}]
        if l_url: payload.append({"type": "image_url", "image_url": {"url": l_url}, "role": "last_frame"})

        status.write("🤖 提交任务...")
        res = client.content_generation.tasks.create(
            model=model_id, content=payload, generate_audio=True,
            ratio=ratio, resolution=resolution, duration=duration
        )
        task_id = res.id
        
        # === 核心：提交成功后，立即保存到本地账本 ===
        save_to_local_db(task_id, prompt_text)
        # ========================================
        
        start = time.time()
        status.write(f"🆔 任务ID: {task_id}")
        
        while True:
            elapsed = int(time.time() - start)
            status.update(label=f"🚀 运行中... ({elapsed}s)", state="running")
            
            if elapsed > 600: status.update(label="超时", state="error"); break
            
            get_res = client.content_generation.tasks.get(task_id=task_id)
            if get_res.status == "succeeded":
                v_url = get_res.content.video_url
                status.update(label=f"✅ 成功 ({elapsed}s)", state="complete", expanded=False)
                
                new_record = {
                    "task_id": task_id,
                    "created_at": time.time(),
                    "time": datetime.now().strftime("%m-%d %H:%M"),
                    "prompt": prompt_text, # 这里直接用当前的 prompt
                    "video_url": v_url,
                    "model": model_id
                }
                st.session_state.history.insert(0, new_record)
                st.balloons()
                st.video(v_url)
                break
            elif get_res.status == "failed":
                status.update(label="失败", state="error"); st.error(get_res.error); break
            
            time.sleep(2) 
            
    except Exception as e: status.update(label="异常", state="error"); st.error(str(e))

# ==========================================
# 6. 历史记录 (网格布局)
# ==========================================
if st.session_state.history:
    st.divider()
    st.subheader(f"📜 历史记录 ({len(st.session_state.history)})")
    
    cols = st.columns(3)
    for index, item in enumerate(st.session_state.history):
        with cols[index % 3]:
            with st.container(border=True):
                st.video(item['video_url'])
                st.caption(f"🕒 {item['time']}")
                
                p_text = item['prompt']
                short_p = p_text[:20] + "..." if len(p_text) > 20 else p_text
                st.markdown(f"**Prompt:** {short_p}")
                
                with st.expander("详情"):
                    # 这里的 prompt 会优先显示我们刚才存进去的
                    st.text_area("完整提示词", item['prompt'], height=80, disabled=True, key=f"t_{index}")
                    st.text(f"ID: {item.get('task_id')}")
                    st.markdown(f"**[📥 下载视频]({item['video_url']})**")
