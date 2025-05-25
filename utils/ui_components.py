import streamlit as st

def render_settings_drawer():
    """Render a slide-out settings drawer and return button states."""
    st.markdown(
        """
        <style>
        .settings-drawer {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            max-width: 480px;
            max-height: 90vh;
            background: rgba(31,31,48,0.95);
            padding: 20px 16px;
            overflow-y: auto;
            z-index: 1001;
            transition: all 0.3s ease-in-out;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            border: 2px solid #8000ff;
            border-radius: 6px;
        }
        .settings-drawer.visible {
            display: block;
        }
        .settings-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            cursor: pointer;
        }
        .settings-overlay.visible {
            display: block;
        }
        .close-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: transparent;
            border: none;
            color: #fafafa;
            font-size: 1.2rem;
            cursor: pointer;
            padding: 5px 10px;
            z-index: 1002;
        }
        .close-btn:hover {
            color: #ff6b6b;
        }
        .settings-content {
            margin-top: 10px;
        }
        </style>
        <script>
        function hideSettingsDrawer() {
            const overlay = document.querySelector('.settings-overlay');
            const drawer = document.querySelector('.settings-drawer');
            if (overlay) overlay.classList.remove('visible');
            if (drawer) drawer.classList.remove('visible');
        }
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideSettingsDrawer();
            }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )

    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False

    st.markdown(
        f"""
        <div class="settings-overlay{'visible' if st.session_state.show_settings else ''}" onclick="hideSettingsDrawer();"></div>
        <div class="settings-drawer{'visible' if st.session_state.show_settings else ''}">
        <button class="close-btn" onclick="hideSettingsDrawer();">✖</button>
        """,
        unsafe_allow_html=True
    )

    if st.session_state.show_settings:
        with st.container():
            st.session_state.test_mode = st.toggle(
                "Test Mode",
                value=st.session_state.get('test_mode', False),
                help="In Test Mode, only Wired.com is scanned",
            )

            col1, col2 = st.columns([2, 2])
            with col1:
                st.session_state.time_value = st.number_input(
                    "Time Period",
                    min_value=1,
                    value=st.session_state.get("time_value", 1),
                    step=1,
                )
            with col2:
                unit_options = ["Days", "Weeks"]
                default_index = unit_options.index(st.session_state.get("time_unit", "Weeks"))
                st.session_state.time_unit = st.selectbox(
                    "Unit",
                    unit_options,
                    index=default_index,
                )

            fetch_button = st.button(
                "Fetch New Articles",
                disabled=st.session_state.get("is_fetching", False),
                type="primary",
                key="fetch_btn",
            )

            config_saved = False
            with st.expander("Configuration", expanded=False):
                from utils.config_manager import load_config, save_config

                config_data = load_config()
                eval_cfg = config_data.get("evaluation", {})

                companies = st.text_area(
                    "Companies (comma separated)",
                    ", ".join(eval_cfg.get("companies", [])),
                )
                tools = st.text_area(
                    "Tools (comma separated)",
                    ", ".join(eval_cfg.get("tools", [])),
                )
                retail_terms = st.text_area(
                    "Retail Terms (comma separated)",
                    ", ".join(eval_cfg.get("retail_terms", [])),
                )
                roi_pattern = st.text_input(
                    "ROI Regex Pattern",
                    eval_cfg.get("roi_pattern", ""),
                )
                promo_pattern = st.text_input(
                    "Promotional Regex Pattern",
                    eval_cfg.get("promotional_pattern", ""),
                )
                deployment_terms = st.text_area(
                    "Deployment Terms (comma separated)",
                    ", ".join(eval_cfg.get("deployment_terms", [])),
                )
                major_platforms = st.text_area(
                    "Major Platforms (comma separated)",
                    ", ".join(eval_cfg.get("major_platforms", [])),
                )
                rubric = st.text_area(
                    "Takeaway Rubric",
                    config_data.get("takeaway_rubric", ""),
                    height=150,
                )

                if st.button("Save Configuration", key="save_config_btn"):
                    eval_cfg["companies"] = [c.strip() for c in companies.split(",") if c.strip()]
                    eval_cfg["tools"] = [t.strip() for t in tools.split(",") if t.strip()]
                    eval_cfg["retail_terms"] = [r.strip() for r in retail_terms.split(",") if r.strip()]
                    eval_cfg["roi_pattern"] = roi_pattern
                    eval_cfg["promotional_pattern"] = promo_pattern
                    eval_cfg["deployment_terms"] = [d.strip() for d in deployment_terms.split(",") if d.strip()]
                    eval_cfg["major_platforms"] = [m.strip() for m in major_platforms.split(",") if m.strip()]
                    config_data["evaluation"] = eval_cfg
                    config_data["takeaway_rubric"] = rubric
                    save_config(config_data)
                    config_saved = True
                    st.success("Configuration saved.")

            return fetch_button, config_saved

    return None, False