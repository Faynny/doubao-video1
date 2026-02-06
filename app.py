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

APP_PASSWORD = "HYMS" 
DB_FILE = "local_prompts.json"

# --- CSS 样式微调：让卡片头部更紧凑 ---
st.markdown("""
<style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f9f9f9; /* 卡片淡灰背景 */
        border-radius: 10px;
        padding: 15px;
    }
    .stButton button {
        border-radius: 8px;
    }
    /* 调整图片标题字体 */
    h3 { font-size: 1.2rem !important; margin-bottom: 0.5rem !important;}
</style>
""", unsafe_allow_html=True)

# ... (登录逻辑保持不变) ...
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

# ... (数据库和上传函数保持不变) ...
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
    local_db = load_local_db()
    if item.id in local_db: return f"📝 {local_db[item.id]}"
    return "☁️ 云端记录 (无提示词)"

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

# ==========================================
# 🔥 核心修改：卡片式图片组件
# ==========================================
def image_card_component(label, key_prefix, icon="🖼️"):
    """
    渲染一个带边框的图片管理卡片
    """
    # 1. 初始化 Session
    gallery_key = f"gallery_{key_prefix}"     # 存所有图片
    selected_key = f"selected_{key_prefix}"   # 存当前选中的那一张
    
    if gallery_key not in st.session_state: st.session_state[gallery_key] = []
    if selected_key not in st.session_state: st.session_state[selected_key] = None

    # 2. 外层容器 (Border=True 实现卡片效果)
    with st.container(border=True):
        st.markdown(f"### {icon} {label}")
        
        # --- A. 核心预览区 (始终显示当前选中的图) ---
        current_file = st.session_state[selected_key]
        
        if current_file:
            st.image(current_file, use_container_width=True)
            # 移除当前图片的按钮
            if st.button(f"❌ 移除图片", key=f"rm_{key_prefix}", use_container_width=True):
                st.session_state[selected_key] = None
                st.rerun()
        else:
            # 占位符：如果没有选图片，显示一个灰色的框
            st.info("尚未选择图片")
            # 或者是搞一个空的占位图，看你喜好
            # st.markdown('<div style="height:200px; background:#eee; text-align:center; line-height:200px; color:#aaa;">暂无图片</div>', unsafe_allow_html=True)

        st.divider()

        # --- B. 操作区 (上传 & 历史) ---
        
        # 1. 上传控件 (使用 label_visibility="collapsed" 隐藏丑陋的 Label)
        uploaded_files = st.file_uploader(
            "上传新图", 
            type=["jpg", "png"], 
            accept_multiple_files=True, 
            key=f"u_{key_prefix}",
            label_visibility="collapsed" # 隐藏标题，让界面更紧凑
        )
        
        # 自动处理新上传
        if uploaded_files:
            for f in uploaded_files:
                # 存入相册
                if len(st.session_state[gallery_key]) < 10:
                    if f.name not in [x.name for x in st.session_state[gallery_key]]:
                        st.session_state[gallery_key].append(f)
                        # 🔥 自动选中最新上传的这张！
                        st.session_state[selected_key] = f
            # 上传完不需要在这里rerun，Streamlit的机制会自动刷新显示上面的 Preview

        # 2. 历史记录折叠菜单
        # 如果相册里有图，才显示这个折叠条
        if st.session_state[gallery_key]:
            with st.expander(f"📚 从历史相册选择 ({len(st.session_state[gallery_key])})"):
                
                # 缩略图展示
                cols = st.columns(4)
                for i, img in enumerate(st.session_state[gallery_key]):
                    with cols[i % 4]:
                        st.image(img, use_container_width=True)
                
                # 选择器
                options = [f.name for f in st.session_state[gallery_key]]
                # 尝试找到当前选中文件的 index
                current_idx = 0
                if current_file and current_file.name in options:
                    current_idx = options.index(current_file.name)
                
                # 单选框
                selected_name = st.radio(
                    "点击选择:", 
                    options, 
                    index=current_idx,
                    key=f"radio_{key_prefix}"
                )
                
                # 更新选中状态
                if selected_name:
                    # 根据名字找到文件对象
                    for f in st.session_state[gallery_key]:
                        if f.name == selected_name:
                            st.session_state[selected_key] = f
                            break
                
                # 清空按钮
                if st.button("🗑️ 清空历史", key=f"clr_{key_prefix}"):
                    st.session_state[gallery_key] = []
                    st.session_state[selected_key] = None
                    st.rerun()

    # 返回给主程序的数据
    if st.session_state[selected_key]:
        return st.session_state[selected_key], "file"
    return None, None


# ==========================================
# 4. 侧边栏配置
# ==========================================
with st.sidebar:
    st.header("⚙️ 全局配置")
    api_key = st.text_input("API Key", value=st.secrets.get("ARK_API_KEY", os.environ.get("ARK_API_KEY", "")), type="password")
    
    st.divider()
    model_id = st.text_input("模型ID", value="doubao-seedance-1-5-pro-251215")
    resolution = st.selectbox("清晰度", ["720p", "1080p"])
    ratio = st.selectbox("比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长", 2, 10, 5)
    
    st.divider()
    if st.button("🔄 同步最近 50 条 (自动匹配)"):
        if not api_key:
            st.error("缺 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("同步中..."):
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
                        st.success(f"同步完成，新增 {count} 条")
            except Exception as e: st.error(str(e))

# ==========================================
# 5. 主界面布局 (上：提示词，下：双卡片)
# ==========================================
st.title("🎬 豆包视频生成 Pro")

# --- 第一行：提示词 ---
st.markdown("##### 1️⃣ 输入视频描述")
prompt_text = st.text_area(
    "提示词", 
    value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", 
    height=100, 
    label_visibility="collapsed", # 隐藏label让界面更干净
    placeholder="在此输入详细的提示词..."
)

st.write("") # 增加一点间距

# --- 第二行：图片上传区 (左右并列，高度对齐) ---
st.markdown("##### 2️⃣ 上传参考图")

col_left, col_right = st.columns([1, 1], gap="medium") # 使用 gap="medium" 增加中间间距

with col_left:
    # 调用我们的新组件 - 首帧
    first_data, first_type = image_card_component("首帧图片 (必选)", "first_frame", icon="🏁")

with col_right:
    # 调用我们的新组件 - 尾帧
    last_data, last_type = image_card_component("尾帧图片 (可选)", "last_frame", icon="🔚")

st.divider()

# ==========================================
# 6. 生成按钮
# ==========================================
# 使用 columns 让按钮居中或者变宽
_, btn_col, _ = st.columns([1, 2, 1])
with btn_col:
    run_btn = st.button("🚀 立即生成视频", use_container_width=True)

if run_btn:
    if not api_key or not first_data: st.error("❌ 缺少 API Key 或 首帧图片"); st.stop()
    
    status = st.status("🚀 任务初始化...", expanded=True)
    try:
        # 上传逻辑
        f_url = upload_to_temp_host(first_data)
        l_url = upload_to_temp_host(last_data) if last_data else None
        
        if not f_url: status.update(label="图片上传失败", state="error"); st.stop()

        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        payload = [{"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": f_url}, "role": "first_frame"}]
        if l_url: payload.append({"type": "image_url", "image_url": {"url": l_url}, "role": "last_frame"})

        status.write("🤖 提交任务...")
        res = client.content_generation.tasks.create(
            model=model_id, content=payload, generate_audio=True,
            ratio=ratio, resolution=resolution, duration=duration
        )
        task_id = res.id
        
        # 保存提示词
        save_to_local_db(task_id, prompt_text)
        
        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            status.update(label=f"🚀 生成中... ({elapsed}s)", state="running")
            if elapsed > 600: status.update(label="超时", state="error"); break
            
            get_res = client.content_generation.tasks.get(task_id=task_id)
            if get_res.status == "succeeded":
                v_url = get_res.content.video_url
                status.update(label=f"✅ 完成！({elapsed}s)", state="complete", expanded=False)
                
                # 插入新记录
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
                status.update(label="失败", state="error"); st.error(get_res.error); break
            time.sleep(2)
            
    except Exception as e: status.update(label="异常", state="error"); st.error(str(e))

# ==========================================
# 7. 历史记录 (网格布局)
# ==========================================
if "history" in st.session_state and st.session_state.history:
    st.divider()
    st.subheader(f"📜 历史作品库 ({len(st.session_state.history)})")
    
    cols = st.columns(3)
    for index, item in enumerate(st.session_state.history):
        with cols[index % 3]:
            with st.container(border=True):
                st.video(item['video_url'])
                
                # 标题处理
                p_text = item['prompt']
                clean_text = p_text.replace("📝 ", "").replace("☁️ ", "")
                short_p = clean_text[:18] + "..." if len(clean_text) > 18 else clean_text
                
                if "📝" in p_text: st.markdown(f"**{short_p}**")
                else: st.caption(short_p)
                
                with st.expander("详细信息"):
                    st.caption(f"🕒 {item['time']}")
                    st.text_area("Prompt", clean_text, height=70, disabled=True, key=f"t_{index}")
                    st.markdown(f"[📥 下载]({item['video_url']})")
