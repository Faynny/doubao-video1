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
# 2. 初始化与辅助函数
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

# --- 核心修复：暴力提取提示词函数 ---
def extract_prompt_from_item(item):
    """
    尝试从 API 返回的复杂对象中提取提示词文本。
    策略：检查 content 列表 -> 检查 input 字段 -> 检查 request 字段
    """
    try:
        # 1. 尝试直接从 content 列表里找 type='text'
        if hasattr(item, 'content') and isinstance(item.content, list):
            for c in item.content:
                # 兼容对象属性访问 (.text) 和字典访问 (['text'])
                if hasattr(c, 'type') and c.type == 'text':
                    return getattr(c, 'text', '')
                if isinstance(c, dict) and c.get('type') == 'text':
                    return c.get('text', '')

        # 2. 有些版本的 SDK 将输入放在 request 或 inputs 字段
        # 这里做一个简单的容错，如果 content 里只有视频，尝试找找别的属性（如果有的话）
        # 目前豆包 API 通常在 content 里回显，但也可能只回显视频。
        
        # 如果实在找不到，返回特定标记
        return "☁️ 云端同步 (未识别到文本)"
    except Exception:
        return "☁️ 解析错误"

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
            options = [f"{i+1}. {f.name}" for i, f in enumerate(st.session_state[gallery_key])]
            sel = st.radio("选择:", options, horizontal=True, key=f"r_{key_prefix}")
            if st.button("清空", key=f"c_{key_prefix}"):
                st.session_state[gallery_key] = []
                st.rerun()
            if sel: return st.session_state[gallery_key][options.index(sel)], "file"
    with tab2:
        url = st.text_input("URL", key=f"url_{key_prefix}")
        if url: return url, "url"
    return None, None

# ==========================================
# 3. 侧边栏 (含同步逻辑)
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
    st.markdown("### ☁️ 云端同步")
    
    if st.button("🔄 同步最近 20 条 (按时间排序)"):
        if not api_key:
            st.error("缺 API Key")
        else:
            try:
                client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
                with st.spinner("正在拉取数据..."):
                    # 1. 获取列表
                    resp = client.content_generation.tasks.list(page_size=20, status="succeeded")
                    count = 0
                    if hasattr(resp, 'items'):
                        for item in resp.items:
                            # 去重
                            if not any(h.get('task_id') == item.id for h in st.session_state.history):
                                # 2. 提取数据
                                prompt_str = extract_prompt_from_item(item)
                                # 获取原始时间戳用于排序
                                created_ts = getattr(item, 'created_at', 0)
                                
                                st.session_state.history.append({
                                    "task_id": item.id,
                                    "created_at": created_ts, # 存原始时间戳
                                    "time": datetime.fromtimestamp(created_ts).strftime("%m-%d %H:%M"),
                                    "prompt": prompt_str,
                                    "video_url": item.content.video_url,
                                    "model": model_id
                                })
                                count += 1
                        
                        # 3. 核心修改：强制按时间倒序排序 (最新的在最前)
                        # key使用 created_at 字段，reverse=True 表示大数(新时间)在前
                        st.session_state.history.sort(key=lambda x: x['created_at'], reverse=True)
                        
                        st.success(f"同步了 {count} 条新记录！")
                    else:
                        st.warning("云端无数据")
            except Exception as e:
                st.error(f"同步出错: {str(e)}")

# ==========================================
# 4. 主界面
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

        status.write("🤖 生成中...")
        res = client.content_generation.tasks.create(
            model=model_id, content=payload, generate_audio=True,
            ratio=ratio, resolution=resolution, duration=duration
        )
        task_id = res.id
        
        start = time.time()
        while True:
            if time.time() - start > 600: status.update(label="超时", state="error"); break
            get_res = client.content_generation.tasks.get(task_id=task_id)
            if get_res.status == "succeeded":
                v_url = get_res.content.video_url
                status.update(label="✅ 成功", state="complete", expanded=False)
                
                # 新生成的直接插到最前面
                new_record = {
                    "task_id": task_id,
                    "created_at": time.time(), # 当前时间
                    "time": datetime.now().strftime("%m-%d %H:%M"),
                    "prompt": prompt_text,
                    "video_url": v_url,
                    "model": model_id
                }
                st.session_state.history.insert(0, new_record) # 插入到第一个位置
                
                st.balloons()
                st.video(v_url)
                break
            elif get_res.status == "failed":
                status.update(label="失败", state="error"); st.error(get_res.error); break
            time.sleep(3)
    except Exception as e: status.update(label="异常", state="error"); st.error(str(e))

# ==========================================
# 5. 历史记录 (直接显示，不用倒序循环了，因为列表本身已经排好了)
# ==========================================
if st.session_state.history:
    st.divider()
    st.subheader(f"📜 历史记录 ({len(st.session_state.history)})")
    
    # 因为列表已经 sort 过了，直接遍历即可
    for item in st.session_state.history:
        p_show = item['prompt'][:30] + "..." if len(item['prompt']) > 30 else item['prompt']
        with st.expander(f"🕒 {item['time']} - {p_show}", expanded=True):
            hc1, hc2 = st.columns([1, 1.5])
            hc1.video(item['video_url'])
            hc2.info(f"📄 **提示词:**\n{item['prompt']}")
            hc2.caption(f"ID: {item.get('task_id')}")
            hc2.markdown(f"[📥 下载]({item['video_url']})")
