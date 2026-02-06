import streamlit as st
import os
import time
import requests
import json
import base64
from datetime import datetime
from volcenginesdkarkruntime import Ark

# ==========================================
# 1. 页面基础配置 (必须在第一行)
# ==========================================
st.set_page_config(
    page_title="豆包视频生成 Pro",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 🔐 安全配置 ===
APP_PASSWORD = "HYMS"       # <--- 请修改你的访问密码
DB_FILE = "local_prompts.json" # 本地提示词数据库文件

# === 🎨 全局样式优化 ===
st.markdown("""
<style>
    /* 让卡片头部更紧凑 */
    h3 { font-size: 1.1rem !important; margin-bottom: 0.5rem !important;}
    
    /* 调整主按钮样式 */
    div.stButton > button:first-child {
        border-radius: 8px;
        font-weight: bold;
    }
    
    /* 修复上传组件的间距 */
    div[data-testid="stFileUploader"] {
        padding-top: 10px;
    }
    
    /* 让历史相册里的文件名显示更紧凑 */
    div[data-testid="stCaptionContainer"] {
        font-size: 12px;
        color: #666;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 登录拦截逻辑
# ==========================================
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
# 3. 本地数据库逻辑
# ==========================================
def load_local_db():
    if not os.path.exists(DB_FILE): return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_to_local_db(task_id, prompt):
    db = load_local_db()
    db[task_id] = prompt
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, ensure_ascii=False, indent=2)
    except: pass

def match_prompt_by_id(item):
    """尝试从本地数据库找回提示词"""
    local_db = load_local_db()
    if item.id in local_db: return f"📝 {local_db[item.id]}"
    return "☁️ 云端记录 (无提示词)"

# ==========================================
# 4. 辅助函数
# ==========================================
def upload_to_temp_host(uploaded_file):
    try:
        uploaded_file.seek(0)
        url = 'https://tmpfiles.org/api/v1/upload'
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(url, files=files)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return None
    except: return None

# ==========================================
# 🔥 核心组件：Base64 修复版图片卡片 (含文件名显示)
# ==========================================
def image_card_component(label, key_prefix, icon="🖼️"):
    """
    渲染一个高度对齐、自动预览的图片管理卡片
    """
    gallery_key = f"gallery_{key_prefix}"
    selected_key = f"selected_{key_prefix}"
    
    if gallery_key not in st.session_state: st.session_state[gallery_key] = []
    if selected_key not in st.session_state: st.session_state[selected_key] = None

    # 外层容器
    with st.container(border=True):
        st.markdown(f"### {icon} {label}")
        
        current_file = st.session_state[selected_key]
        
        # --- A. 预览区 (固定高度 200px) ---
        if current_file:
            try:
                current_file.seek(0)
                b64_data = base64.b64encode(current_file.read()).decode()
                mime_type = current_file.type
                current_file.seek(0)
                
                st.markdown(
                    f"""
                    <div style="
                        height: 200px; 
                        width: 100%; 
                        background-color: #f0f2f6; 
                        border-radius: 8px; 
                        display: flex; 
                        justify-content: center; 
                        align-items: center; 
                        overflow: hidden;
                        margin-bottom: 10px;
                    ">
                        <img src="data:{mime_type};base64,{b64_data}" 
                             style="max-height: 100%; max-width: 100%; object-fit: contain;">
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                if st.button(f"❌ 移除图片", key=f"rm_{key_prefix}", use_container_width=True):
                    st.session_state[selected_key] = None
                    st.rerun()
            except:
                st.error("预览失败")
                st.session_state[selected_key] = None
        else:
            # 占位符
            st.markdown(
                f"""
                <div style="
                    height: 200px; 
                    width: 100%; 
                    background-color: #fafafa; 
                    border-radius: 8px; 
                    border: 2px dashed #ddd; 
                    display: flex; 
                    flex-direction: column; 
                    justify-content: center; 
                    align-items: center; 
                    color: #ccc;
                    margin-bottom: 10px;
                ">
                    <div style="font-size: 30px;">📷</div>
                    <div style="font-size: 14px; margin-top: 5px;">暂无图片</div>
                </div>
                """, 
                unsafe_allow_html=True
            )
            st.button("❌ 移除图片", key=f"rm_dis_{key_prefix}", disabled=True, use_container_width=True)

        st.divider()

        # --- B. 操作区 ---
        uploaded_files = st.file_uploader(
            "上传新图", 
            type=["jpg", "png"], 
            accept_multiple_files=True, 
            key=f"u_{key_prefix}",
            label_visibility="collapsed"
        )
        
        if uploaded_files:
            new_upload = False
            for f in uploaded_files:
                if len(st.session_state[gallery_key]) < 10:
                    names = [x.name for x in st.session_state[gallery_key]]
                    if f.name not in names:
                        st.session_state[gallery_key].append(f)
                        st.session_state[selected_key] = f
                        new_upload = True
            if new_upload:
                st.rerun()

        # 📚 历史相册 (带文件名显示)
        if st.session_state[gallery_key]:
            with st.expander(f"📚 历史相册 ({len(st.session_state[gallery_key])})"):
                cols = st.columns(4)
                for i, img in enumerate(st.session_state[gallery_key]):
                    with cols[i % 4]:
                        st.image(img, use_container_width=True)
                        # 🔥 核心修改：在图片下方显示文件名
                        # help参数会在鼠标悬停时显示完整文件名，防止过长截断看不清
                        st.caption(img.name, help=img.name) 
                
                options = [f.name for f in st.session_state[gallery_key]]
                current_idx = 0
                if current_file and current_file.name in options:
                    current_idx = options.index(current_file.name)
                
                selected_name = st.radio("选择:", options, index=current_idx, key=f"radio_{key_prefix}", label_visibility="collapsed")
                
                if selected_name:
                    for f in st.session_state[gallery_key]:
                        if f.name == selected_name:
                            if st.session_state[selected_key] != f:
                                st.session_state[selected_key] = f
                                st.rerun()
                            break
                
                if st.button("🗑️ 清空历史", key=f"clr_{key_prefix}"):
                    st.session_state[gallery_key] = []
                    st.session_state[selected_key] = None
                    st.rerun()

    if st.session_state[selected_key]:
        return st.session_state[selected_key], "file"
    return None, None


# ==========================================
# 5. 侧边栏配置
# ==========================================
with st.sidebar:
    st.header("⚙️ 全局配置")
    
    default_key = st.secrets.get("ARK_API_KEY", os.environ.get("ARK_API_KEY", ""))
    api_key = st.text_input("API Key", value=default_key, type="password")
    
    st.divider()
    model_id = st.text_input("模型ID", value="doubao-seedance-1-5-pro-251215")
    resolution = st.selectbox("清晰度", ["720p", "1080p"])
    ratio = st.selectbox("比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长", 2, 10, 5)
    
    st.divider()
    # 🔄 同步逻辑
    if st.button("🔄 同步最近 50 条 (智能匹配)"):
        if not api_key:
            st.error("缺 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在同步云端数据并匹配本地记录..."):
                    if "history" not in st.session_state: st.session_state.history = []
                    
                    resp = client.content_generation.tasks.list(page_size=50, status="succeeded")
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            if not any(h.get('task_id') == item.id for h in st.session_state.history):
                                matched_prompt = match_prompt_by_id(item)
                                ts = getattr(item, 'created_at', 0)
                                
                                st.session_state.history.append({
                                    "task_id": item.id,
                                    "created_at": ts,
                                    "time": datetime.fromtimestamp(ts).strftime("%m-%d %H:%M"),
                                    "prompt": matched_prompt,
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        st.session_state.history.sort(key=lambda x: x['created_at'], reverse=True)
                        st.success(f"同步完成，新增 {count} 条记录")
                    else: st.warning("未找到记录")
            except Exception as e: st.error(str(e))

# ==========================================
# 6. 主界面布局
# ==========================================
st.title("🎬 豆包视频生成 Pro")

st.markdown("##### 1️⃣ 输入视频描述")
prompt_text = st.text_area(
    "提示词", 
    value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", 
    height=100, 
    label_visibility="collapsed",
    placeholder="在此输入提示词..."
)
st.write("") 

st.markdown("##### 2️⃣ 上传参考图")
col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    first_data, first_type = image_card_component("首帧图片 (必选)", "first_frame", icon="🏁")

with col_right:
    last_data, last_type = image_card_component("尾帧图片 (可选)", "last_frame", icon="🔚")

st.divider()

# --- 生成按钮 ---
_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    run_btn = st.button("🚀 立即生成视频", use_container_width=True, type="primary")

# ==========================================
# 7. 生成执行逻辑
# ==========================================
if run_btn:
    if not api_key: st.error("❌ 请先在侧边栏配置 API Key"); st.stop()
    if not first_data: st.error("❌ 请上传首帧图片"); st.stop()
    
    status = st.status("🚀 任务初始化...", expanded=True)
    try:
        first_data.seek(0)
        f_url = upload_to_temp_host(first_data)
        
        l_url = None
        if last_data:
            last_data.seek(0)
            l_url = upload_to_temp_host(last_data)
        
        if not f_url: status.update(label="图片上传失败", state="error"); st.stop()

        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": f_url}, "role": "first_frame"}]
        if l_url: payload.append({"type": "image_url", "image_url": {"url": l_url}, "role": "last_frame"})

        status.write("🤖 正在提交任务...")
        res = client.content_generation.tasks.create(
            model=model_id, content=payload, generate_audio=True,
            ratio=ratio, resolution=resolution, duration=duration
        )
        task_id = res.id
        
        save_to_local_db(task_id, prompt_text)
        
        start = time.time()
        status.write(f"🆔 任务ID: {task_id}")
        
        while True:
            elapsed = int(time.time() - start)
            status.update(label=f"🚀 生成中... ({elapsed}s)", state="running")
            
            if elapsed > 600: status.update(label="❌ 生成超时", state="error"); break
            
            get_res = client.content_generation.tasks.get(task_id=task_id)
            if get_res.status == "succeeded":
                v_url = get_res.content.video_url
                status.update(label=f"✅ 成功 ({elapsed}s)", state="complete", expanded=False)
                
                new_rec = {
                    "task_id": task_id, "created_at": time.time(),
                    "time": datetime.now().strftime("%m-%d %H:%M"),
                    "prompt": prompt_text, "video_url": v_url, "model": model_id
                }
                if "history" not in st.session_state: st.session_state.history = []
                st.session_state.history.insert(0, new_rec)
                
                st.balloons()
                st.video(v_url)
                break
            elif get_res.status == "failed":
                status.update(label="❌ 失败", state="error"); st.error(get_res.error); break
            
            time.sleep(2)
            
    except Exception as e: status.update(label="异常", state="error"); st.error(str(e))

# ==========================================
# 8. 历史记录 (网格布局)
# ==========================================
if "history" in st.session_state and st.session_state.history:
    st.divider()
    st.subheader(f"📜 历史作品库 ({len(st.session_state.history)})")
    
    cols = st.columns(3)
    for index, item in enumerate(st.session_state.history):
        with cols[index % 3]:
            with st.container(border=True):
                st.video(item['video_url'])
                
                p_text = item['prompt']
                clean_text = p_text.replace("📝 ", "").replace("☁️ ", "")
                short_p = clean_text[:18] + "..." if len(clean_text) > 18 else clean_text
                
                if "📝" in p_text: st.markdown(f"**{short_p}**")
                else: st.caption(short_p)
                
                with st.expander("详细信息"):
                    st.caption(f"🕒 {item['time']}")
                    st.text_area("Prompt", clean_text, height=70, disabled=True, key=f"t_{index}")
                    st.markdown(f"[📥 下载视频]({item['video_url']})")
