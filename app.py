# --- 升级版：带相册功能的图片输入组件 ---
def handle_image_input(label, key_prefix):
    st.markdown(f"**{label}**")
    
    # 初始化该组件的相册 Session State
    gallery_key = f"gallery_{key_prefix}"
    if gallery_key not in st.session_state:
        st.session_state[gallery_key] = []

    tab1, tab2 = st.tabs(["🖼️ 图片库 (本地上传)", "🔗 粘贴链接"])

    # === Tab 1: 本地图片库模式 ===
    with tab1:
        # 1. 上传区 (支持多选)
        uploaded_files = st.file_uploader(
            f"上传图片 (最多存10张) - {key_prefix}", 
            type=["jpg", "png", "jpeg"], 
            accept_multiple_files=True, # 允许一次选多张
            key=f"uploader_{key_prefix}"
        )
        
        # 2. 将新上传的文件加入相册 (去重逻辑简化版：只追加)
        if uploaded_files:
            for new_file in uploaded_files:
                # 简单检查是否超过 10 张
                if len(st.session_state[gallery_key]) < 10:
                    # 避免重复添加 (通过文件名判断)
                    current_names = [f.name for f in st.session_state[gallery_key]]
                    if new_file.name not in current_names:
                        st.session_state[gallery_key].append(new_file)
                else:
                    st.caption("⚠️ 相册已满 (10张)，新图片未添加")
        
        # 3. 显示相册管理区
        if len(st.session_state[gallery_key]) > 0:
            st.divider()
            st.markdown(f"**📚 当前相册 ({len(st.session_state[gallery_key])}/10)**")
            
            # 使用 Radio 组件来选择
            # 生成选项列表：例如 ["图片1: cat.jpg", "图片2: dog.jpg"]
            options = [f"{i+1}. {f.name}" for i, f in enumerate(st.session_state[gallery_key])]
            
            selected_option = st.radio(
                "请选择一张作为输入：",
                options,
                horizontal=True, # 横向排列
                key=f"radio_{key_prefix}"
            )
            
            # 清空按钮
            if st.button(f"🗑️ 清空相册 ({key_prefix})", key=f"clear_{key_prefix}"):
                st.session_state[gallery_key] = []
                st.rerun() # 立即刷新界面
            
            # 找到被选中的那个文件对象
            if selected_option:
                index = options.index(selected_option)
                selected_file = st.session_state[gallery_key][index]
                
                # 显示大图预览
                st.image(selected_file, caption="✅ 当前选中", width=250)
                return selected_file, "file"
        else:
            st.info("👈 请上传图片，它们会保留在这里供你选择。")

    # === Tab 2: URL 模式 (保持不变) ===
    image_url = None
    with tab2:
        url_input = st.text_input(f"URL ({key_prefix})", key=f"url_{key_prefix}", placeholder="https://...")
        if url_input:
            image_url = url_input
    
    if image_url:
        st.image(image_url, width=200)
        return image_url, "url"
    
    return None, None
