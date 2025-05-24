import streamlit as st


def render_settings_drawer():
    """Render a slide-out settings drawer and return button states."""
    st.markdown(
        """
        <style>
        .settings-drawer {
            position: fixed;
            top: 0;
            left: 0;
            width: 320px;
            height: 100vh;
            background: rgba(31,31,48,0.95);
            padding: 20px 16px;
            overflow-y: auto;
            z-index: 1000;
            transition: transform 0.3s ease-in-out;
            backdrop-filter: blur(10px);
            box-shadow: 2px 0 5px rgba(0,0,0,0.2);
            transform: translateX(-100%);
            visibility: hidden;
        }
        #close_settings_btn button {
            float: right;
            background: transparent;
            border: none;
            color: #fafafa;
            font-size: 1.2rem;
            cursor: pointer;
        }
        #close_settings_btn button:hover {
            color: #ff6b6b;
        }
        .drawer-visible {
            transform: translateX(0);
            visibility: visible;
        }
        .settings-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100vh;
            background: rgba(0,0,0,0.5);
            z-index: 999;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease-in-out;
        }
        .overlay-visible {
            opacity: 1;
            visibility: visible;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    drawer_visible = st.session_state.get("show_settings", False)
    drawer_class = "drawer-visible" if drawer_visible else ""
    overlay_class = "overlay-visible" if drawer_visible else ""
    st.markdown(
        f"<div id='settings-overlay' class='settings-overlay {overlay_class}'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div id='settings-drawer' class='settings-drawer {drawer_class}'>",
        unsafe_allow_html=True,
    )

    _, close_col = st.columns([5, 1])
    with close_col:
        if st.button("✖", key="close_settings_btn", help="Close settings", type="secondary"):
            st.session_state.show_settings = False
            st.rerun()

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

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <script>
        const overlay = document.getElementById('settings-overlay');

        if (drawer && overlay) {{
            {'drawer.classList.add("drawer-visible"); overlay.classList.add("overlay-visible");' if drawer_visible else 'drawer.classList.remove("drawer-visible"); overlay.classList.remove("overlay-visible");'}
            overlay.addEventListener('click', () => {{
                const btn = document.querySelector('#close_settings_btn button');
                if (btn) btn.click();
            }});
        }}
        </script>
        """,
        unsafe_allow_html=True,
    )
    return fetch_button, config_saved
