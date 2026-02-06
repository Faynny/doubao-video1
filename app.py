# ... (前面的引用保持不变) ...

# ==========================================
# 🔥 核心修改：卡片式图片组件 (修复预览与对齐)
# ==========================================
def image_card_component(label, key_prefix, icon="🖼️"):
    """
    渲染一个带边框的图片管理卡片
    """
    gallery_key = f"gallery_{key_prefix}"
    selected_key = f"selected_{key_prefix}"
    
    if gallery_key not in st.session_state: st.session_state[gallery_key] = []
    if selected_key not in st.session_state: st.session_state[selected_key] = None

    # 外层容器
    with st.container(border=True):
        st.markdown(f"### {icon} {label}")
        
        # --- A. 预览区 (强制固定高度 250px，保证左右对齐) ---
        current_file = st.session_state[selected_key]
        
        # 使用 CSS 创建一个固定高度的容器，防止页面跳动
        preview_container = st.container()
        
        with preview_container:
            if current_file:
                # 显示图片，并限制最大高度，防止把卡片撑得太长
                # 注意：Streamlit 原生 image 很难精准控制 px 高度，这里用样式微调
                st.markdown(
                    f'<div style="height: 250px; display: flex; align-items: center; justify-content: center; overflow: hidden; background-color: #f0f2f6; border-radius: 8px;">', 
                    unsafe_allow_html=True
                )
                st.image(current_file, use_container_width=True) # 图片自适应宽度
                st.markdown('</div>', unsafe_allow_html=True)
                
                # 移除按钮紧贴图片下方
                if st.button(f"❌ 移除图片", key=f"rm_{key_prefix}", use_container_width=True):
                    st.session_state[selected_key] = None
                    st.rerun()
            else:
                # 占位符：没有图片时，显示一个同样 250px 高的灰色框
                st.markdown(
                    f"""
                    <div style="height: 250px; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #f0f2f6; border-radius: 8px; color: #888; border: 2px dashed #ccc;">
                        <div style="font-size: 40px;">📷</div>
                        <div style="margin-top: 10px;">暂无图片预览</div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                # 占位按钮，为了保持高度一致，也可以放个禁用的假按钮，或者留空
                st.button("❌ 移除图片", key=f"rm_disabled_{key_prefix}", disabled=True, use_container_width=True)

        st.divider()

        # --- B. 操作区 ---
        uploaded_files = st.file_uploader(
            "上传新图", 
            type=["jpg", "png"], 
            accept_multiple_files=True, 
            key=f"u_{key_prefix}",
            label_visibility="collapsed"
        )
        
        # 自动处理新上传
        if uploaded_files:
            new_upload = False
            for f in uploaded_files:
                if len(st.session_state[gallery_key]) < 10:
                    # 检查重名，防止重复添加
                    existing_names = [x.name for x in st.session_state[gallery_key]]
                    if f.name not in existing_names:
                        st.session_state[gallery_key].append(f)
                        st.session_state[selected_key] = f
                        new_upload = True
            
            # 🔥 关键修复：如果有新图片上传，立即刷新页面！
            # 这样上面的预览区就能立刻显示出刚才上传的图，不会慢半拍了
            if new_upload:
                st.rerun()

        # 历史记录折叠菜单
        if st.session_state[gallery_key]:
            with st.expander(f"📚 历史相册 ({len(st.session_state[gallery_key])})"):
                cols = st.columns(4)
                for i, img in enumerate(st.session_state[gallery_key]):
                    with cols[i % 4]:
                        st.image(img, use_container_width=True)
                
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
                
                if st.button("🗑️ 清空", key=f"clr_{key_prefix}"):
                    st.session_state[gallery_key] = []
                    st.session_state[selected_key] = None
                    st.rerun()

    if st.session_state[selected_key]:
        return st.session_state[selected_key], "file"
    return None, None
