import streamlit as st
import os
import time
import requests
from volcenginesdkarkruntime import Ark

# 设置页面配置
st.set_page_config(page_title="豆包视频生成器 (含上传功能)", layout="wide")

st.title("🎬 豆包视频生成 (Pro版)")
st.markdown("支持本地图片上传 -> 自动转 URL -> 生成视频")

# --- 辅助函数：上传本地文件到 tmpfiles.org ---
def upload_to_temp_host(uploaded_file):
    """
    将文件上传到 tmpfiles.org 并获取直链
    """
    try:
        # 使用 tmpfiles.org 的 API
        url = 'https://tmpfiles.org/api/v1/upload'
        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        response = requests.post(url, files=files)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                original_url = data['data']['url']
                # 关键步骤：tmpfiles.org 返回的地址是预览页，
                # 需要把 /tmpfiles.org/ 替换为 /tmpfiles.org/dl/ 才是图片直链
                direct_url = original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                return direct_url
        return None
    except Exception as e:
        st.error(f"图片上传失败: {e}")
        return None

# --- 组件封装：处理图片输入（URL 或 本地上传）---
def handle_image_input(label, key_prefix):
    """
    创建一个选项卡，让用户选择输入 URL 还是上传图片
    返回: (最终的图片URL, 是否有输入)
    """
    st.markdown(f"**{label}**")
    tab1, tab2 = st.tabs(["🔗 输入 URL", "📤 上传本地图片"])
    
    image_url = None
    
    with tab1:
        url_input = st.text_input(f"粘贴链接 ({key_prefix})", key=f"url_{key_prefix}")
        if url_input:
            image_url = url_input
            
    with tab2:
        file_input = st.file_uploader(f"选择图片 ({key_prefix})", type=["jpg", "jpeg", "png"], key=f"file_{key_prefix}")
        if file_input:
            # 预览本地图片
            st.image(file_input, caption="本地预览", width=200)
            st.info("💡 点击生成时，这张图片将自动上传以获取 URL")
            # 将文件对象暂时存储，点击生成按钮时再上传
            return file_input, "file"
            
    if image_url:
        st.image(image_url, caption="网络预览", width=200)
        return image_url, "url"
    
    return None, None

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 配置参数")
    default_key = os.environ.get("ARK_API_KEY", "")
    api_key = st.text_input("ARK_API_KEY", value=default_key, type="password")
    model_id = st.text_input("Model ID", value="doubao-seedance-1-5-pro-251215")
    ratio = st.selectbox("视频比例", ["adaptive", "16:9", "9:16", "1:1"])
    duration = st.slider("时长 (秒)", 2, 10, 5)

# --- 主界面 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 画面设置")
    prompt_text = st.text_area("提示词", value="图中女孩对着镜头说\"茄子\"，360度环绕运镜", height=120)
    
    st.divider()
    
    # 获取首帧输入
    first_frame_data, first_frame_type = handle_image_input("首帧图片 (必选)", "first")

with col2:
    st.subheader("2. 补充设置")
    # 获取尾帧输入
    last_frame_data, last_frame_type = handle_image_input("尾帧图片 (可选)", "last")

st.divider()

# --- 生成逻辑 ---
if st.button("🚀 开始生成视频", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ 请输入 API Key")
        st.stop()
    
    if not first_frame_data:
        st.error("❌ 必须提供首帧图片")
        st.stop()

    status_box = st.status("正在处理任务...", expanded=True)
    
    try:
        # 1. 处理图片上传（如果有本地文件）
        final_first_url = first_frame_data
        final_last_url = last_frame_data

        if first_frame_type == "file":
            status_box.write("📤 正在上传首帧图片到中转服务器...")
            final_first_url = upload_to_temp_host(first_frame_data)
            if not final_first_url:
                status_box.update(label="上传失败", state="error")
                st.stop()
            status_box.write(f"✅ 首帧已转为链接: {final_first_url}")

        if last_frame_type == "file" and last_frame_data:
            status_box.write("📤 正在上传尾帧图片到中转服务器...")
            final_last_url = upload_to_temp_host(last_frame_data)
            if not final_last_url:
                status_box.update(label="上传失败", state="error")
                st.stop()
            status_box.write(f"✅ 尾帧已转为链接: {final_last_url}")

        # 2. 调用火山引擎 API
        client = Ark(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=api_key)
        
        content_payload = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": final_first_url}, "role": "first_frame"}
        ]
        
        if final_last_url:
            content_payload.append(
                {"type": "image_url", "image_url": {"url": final_last_url}, "role": "last_frame"}
            )

        status_box.write("🤖 正在提交生成任务给豆包模型...")
        create_result = client.content_generation.tasks.create(
            model=model_id,
            content=content_payload,
            generate_audio=True,
            ratio=ratio,
            duration=duration,
            watermark=False,
        )
        task_id = create_result.id
        status_box.write(f"🆔 任务ID: `{task_id}` - 等待生成中...")

        # 3. 轮询
        start_time = time.time()
        while True:
            if time.time() - start_time > 600:
                status_box.update(label="任务超时", state="error")
                break

            get_result = client.content_generation.tasks.get(task_id=task_id)
            status = get_result.status
            
            if status == "succeeded":
                video_url = get_result.content.video_url
                status_box.update(label="生成成功！", state="complete", expanded=False)
                st.balloons()
                st.success("🎉 视频生成完成！")
                st.video(video_url)
                break
            elif status == "failed":
                status_box.update(label="任务失败", state="error")
                st.error(f"Error: {get_result.error}")
                break
            else:
                time.sleep(3)

    except Exception as e:
        status_box.update(label="发生系统错误", state="error")

        st.error(str(e))
