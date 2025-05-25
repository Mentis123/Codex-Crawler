
import streamlit as st

def render_settings_drawer():
    """Render a slide-out settings drawer and return button states."""
    st.markdown(
        """
        <style>
        .settings-drawer {
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
            transition: opacity 0.3s ease-in-out;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 5px rgba(0,0,0,0.2);
            border: 2px solid #8000ff;
            border-radius: 6px;
        }
        .settings-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            transition: all 0.3s ease-in-out;
        }
        .settings-drawer:not(.visible), .settings-overlay:not(.visible) {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }
        .settings-drawer.visible, .settings-overlay.visible {
            opacity: 1;
            visibility: visible;
            pointer-events: auto;
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
        }
        .close-btn:hover {
            color: #ff6b6b;
        }
        .settings-content {
            margin-top: 20px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    drawer_visible = st.session_state.get("show_settings", False)
    visibility_class = "visible" if drawer_visible else ""

    st.markdown(
        f"""
        <div class="settings-overlay {visibility_class}" id="settings-overlay"></div>
        <div class="settings-drawer {visibility_class}" id="settings-drawer">
            <button class="close-btn" id="close-settings-btn">✖</button>
            <div class="settings-content">
                <h3>Settings</h3>
            </div>
        </div>
        <script>
            (function() {{
                const drawer = document.getElementById('settings-drawer');
                const overlay = document.getElementById('settings-overlay');
                const closeBtn = document.getElementById('close-settings-btn');
                
                function closeDrawer() {{
                    const closeButton = window.parent.document.querySelector('button[kind="secondary"]');
                    if (closeButton) closeButton.click();
                }}
                
                if (closeBtn) {{
                    closeBtn.addEventListener('click', closeDrawer);
                }}
                
                if (overlay) {{
                    overlay.addEventListener('click', closeDrawer);
                }}
                
                document.addEventListener('keydown', (e) => {{
                    if (e.key === 'Escape') {{
                        closeDrawer();
                    }}
                }});
            }})();
        </script>
        """,
        unsafe_allow_html=True
    )

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
            disabled=st.session_state.is_fetching,
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
