import streamlit as st
from utils.common import calculate_lookback_days


def _close_settings_param_check():
    """Check query params to determine if the settings drawer should be closed."""
    params = st.query_params  # newer API
    if params.get("close_settings") == "1":
        st.session_state.show_settings = False
        if "close_settings" in params:
            del st.query_params["close_settings"]


def render_settings_drawer():
    """Render a slide-out settings drawer and return button states."""
    _close_settings_param_check()
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
        .settings-content {
            margin-top: 10px;
        }
        .close-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            background: transparent;
            border: none;
            color: #ffffff;
            font-size: 20px;
            cursor: pointer;
        }
        </style>
        <script>
        window.hideSettingsDrawer = function() {
            const url = new URL(window.location.href);
            url.searchParams.set('close_settings', '1');
            window.location.href = url.toString();
        }
        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                window.hideSettingsDrawer();
            }
        });
        </script>
        """,
        unsafe_allow_html=True,
    )

    if "show_settings" not in st.session_state:
        st.session_state.show_settings = False
    if "show_url_modal" not in st.session_state:
        st.session_state.show_url_modal = False

    st.markdown(
        f"""
        <div class="settings-overlay{'visible' if st.session_state.show_settings else ''}" onclick="window.hideSettingsDrawer();"></div>
        <div class="settings-drawer{'visible' if st.session_state.show_settings else ''}">
            <button class="close-btn" onclick="window.hideSettingsDrawer();">&times;</button>
        """,
        unsafe_allow_html=True
    )

    if st.session_state.show_settings:
        with st.container():
            st.toggle(
                "Test Mode",
                value=st.session_state.get('test_mode', False),
                key="test_mode",
                help="In Test Mode, only TechCrunch is scanned",
            )

            col1, col2 = st.columns([2, 2])
            with col1:
                st.number_input(
                    "Time Period",
                    min_value=1,
                    step=1,
                    value=st.session_state.get("time_value", 1),
                    key="time_value",
                )
            with col2:
                unit_options = ["Days", "Weeks"]
                default_index = unit_options.index(st.session_state.get("time_unit", "Weeks"))
                st.selectbox(
                    "Unit",
                    unit_options,
                    index=default_index,
                    key="time_unit",
                )

            st.session_state.lookback_days = calculate_lookback_days(
                st.session_state.time_value,
                st.session_state.time_unit,
            )

            fetch_button = st.button(
                "Fetch New Articles",
                disabled=st.session_state.get("is_fetching", False),
                type="primary",
                key="fetch_btn",
            )
            url_button = st.button(
                "URL Management",
                disabled=st.session_state.get("is_fetching", False),
                type="primary",
                key="url_mgmt_btn",
            )
            if fetch_button:
                # Hide the drawer immediately when starting a fetch
                st.session_state.show_settings = False
                st.markdown(
                    "<script>window.hideSettingsDrawer && window.hideSettingsDrawer();</script>",
                    unsafe_allow_html=True,
                )
            if url_button:
                st.session_state.show_url_modal = True

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
                    eval_cfg["deployment_terms"] = [d.strip() for d in deployment_terms.split(",") if d.strip()]
                    eval_cfg["major_platforms"] = [m.strip() for m in major_platforms.split(",") if m.strip()]
                    config_data["evaluation"] = eval_cfg
                    config_data["takeaway_rubric"] = rubric
                    save_config(config_data)
                    config_saved = True
                    st.success("Configuration saved.")

            if st.session_state.show_url_modal:
                from utils.config_manager import load_config, save_config
                cfg = load_config()
                full_default = "\n".join(cfg.get("full_scan_urls", []))
                test_default = "\n".join(cfg.get("test_scan_urls", []))
                with st.modal("URL Management"):
                    with st.form("url_mgmt_form"):
                        left, right = st.columns(2)
                        full_text = left.text_area("Full Scan URLs", full_default, height=300)
                        test_text = right.text_area("Test Scan URLs", test_default, height=300)
                        saved = st.form_submit_button("Save")
                    if saved:
                        cfg["full_scan_urls"] = [u.strip() for u in full_text.splitlines() if u.strip()]
                        cfg["test_scan_urls"] = [u.strip() for u in test_text.splitlines() if u.strip()]
                        save_config(cfg)
                        st.session_state.show_url_modal = False
                        st.success("URL configuration saved.")
                    st.button("Close", key="close_url_modal", on_click=lambda: st.session_state.update({"show_url_modal": False}))
            return fetch_button, config_saved

    return None, False
