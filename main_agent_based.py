import streamlit as st
from datetime import datetime
import logging

# Import the new agent-based components
from agents.orchestrator import Orchestrator
from utils.simple_particles import add_simple_particles
from utils.report_tools import sort_by_assessment_and_score
from utils.common import calculate_lookback_days

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session state if needed
if 'initialized' not in st.session_state:
    try:
        logger.info("Initializing session state")
        st.session_state.articles = []
        st.session_state.selected_articles = []
        st.session_state.scan_status = []
        st.session_state.test_mode = False
        st.session_state.processing_time = None
        st.session_state.processed_urls = set()
        st.session_state.is_fetching = False
        st.session_state.pdf_data = None
        st.session_state.csv_data = None
        st.session_state.excel_data = None
        st.session_state.show_settings = True  # Display settings modal on first load
        st.session_state.time_value = 1  # Default time period value
        st.session_state.time_unit = "Weeks"  # Default time period unit
        st.session_state.lookback_days = calculate_lookback_days(
            st.session_state.time_value, st.session_state.time_unit
        )
        st.session_state.initialized = True
        st.session_state.last_update = datetime.now()
        st.session_state.scan_complete = False
        st.session_state.current_articles = []
        
        # New agent-based workflow components
        default_config = {
            'crawler_config': {
                'max_crawler_workers': 3,
                'cache_duration_hours': 6,
                'request_timeout': 10,
                'max_retries': 3
            },
            'analyzer_config': {
                'cache_duration_hours': 12,
                'model': 'gpt-4o'
            },
            'report_config': {
                'max_report_articles': 10
            }
        }
        st.session_state.orchestrator_config = default_config
        st.session_state.orchestrator = Orchestrator(default_config)
        logger.info("Session state initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing session state: {str(e)}")
        st.error("Error initializing application. Please refresh the page.")

# Set page config
st.set_page_config(
    page_title="AI News Aggregator",
    layout="wide",
    initial_sidebar_state="expanded"
)

def update_status(message):
    """Updates the processing status in the Streamlit UI."""
    current_time = datetime.now().strftime("%H:%M:%S")
    status_msg = f"[{current_time}] {message}"
    st.session_state.scan_status.insert(0, status_msg)

def render_criteria_dashboard(criteria):
    """Render a styled criteria dashboard below each article."""
    if not criteria:
        return

    st.markdown(
        """
        <style>
        .criteria-table {width:100%; border-collapse:collapse; margin-bottom:5px;}
        .criteria-table th, .criteria-table td {border:1px solid #555; padding:4px 6px; font-size:12px;}
        .criteria-table th {background-color:#31333F; color:#fff;}
        .status-true {color:#21ba45; font-weight:bold; text-align:center;}
        .status-false {color:#db2828; font-weight:bold; text-align:center;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    rows = "".join(
        f"<tr><td>{c.get('criteria')}</td><td class='{'status-true' if c.get('status') else 'status-false'}'>{'✅' if c.get('status') else '❌'}</td><td>{c.get('notes')}</td></tr>"
        for c in criteria
    )
    html = f"<table class='criteria-table'><thead><tr><th>Criteria</th><th>Status</th><th>Notes</th></tr></thead><tbody>{rows}</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

def render_assessment_box(assessment: str, score: int):
    """Display assessment and score in a small colored box."""
    color_map = {"INCLUDE": "#21ba45", "OK": "#f2c037", "CUT": "#db2828"}
    color = color_map.get(assessment, "#cccccc")
    st.markdown(
        f"<div style='border:1px solid {color}; padding:6px 10px; border-radius:4px; display:inline-block; margin-bottom:10px;'>"
        f"<b>Assessment:</b> <span style='color:{color}'>{assessment}</span> &nbsp; "
        f"<b>Score:</b> {score}%"
        "</div>",
        unsafe_allow_html=True,
    )

def main():
    try:
        # Add background effect
        add_simple_particles()

        st.title("GAI Insights Crocs Monitoring Service")

        # Floating settings button and modal
        st.markdown(
            """
            <style>
            .settings-btn {position: fixed; top: 15px; right: 15px; z-index: 1000;}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div class='settings-btn'>", unsafe_allow_html=True)
        if st.button("⚙️", key="settings_btn", help="Settings", type="secondary"):
            st.session_state.show_settings = not st.session_state.show_settings
        st.markdown("</div>", unsafe_allow_html=True)

        from utils.ui_components import render_settings_drawer

        fetch_button, _ = render_settings_drawer()

        # Create container for results
        results_section = st.container()

        # Clear previous results when starting a new fetch
        if fetch_button:
            st.session_state.show_settings = False
            st.query_params["close_settings"] = "1"
            st.session_state.is_fetching = True
            st.session_state.orchestrator = Orchestrator(
                st.session_state.get('orchestrator_config', {})
            )
            st.session_state.pdf_data = None
            st.session_state.csv_data = None
            st.session_state.excel_data = None
            st.session_state.scan_complete = False
            st.session_state.articles = []
            st.session_state.scan_status = []
            st.rerun()

        # Process articles using the agent-based architecture
        if fetch_button or st.session_state.is_fetching:
            try:
                # Load sources
                sources = st.session_state.orchestrator.load_sources(test_mode=st.session_state.test_mode)
                
                # Show progress indicator
                progress_bar = st.progress(0)
                status_container = st.empty()
                
                with st.spinner("Processing news sources..."):
                    # Run the orchestrated workflow
                    result = st.session_state.orchestrator.run_workflow(
                        sources,
                        lookback_days=st.session_state.lookback_days
                    )
                    
                    # Update UI with status messages
                    st.session_state.scan_status = result['status']
                    
                    # Store results in session state
                    if result['success']:
                        st.session_state.articles = result['articles']
                        st.session_state.selected_articles = result.get('selected_articles', [])
                        st.session_state.pdf_data = result['reports'].get('pdf')
                        st.session_state.csv_data = result['reports'].get('csv')
                        st.session_state.excel_data = result['reports'].get('excel')
                        st.session_state.processing_time = result['execution_time']
                        st.session_state.scan_complete = True
                        st.session_state.current_articles = sort_by_assessment_and_score(
                            st.session_state.selected_articles.copy()
                        )
                    else:
                        st.error(f"An error occurred: {result.get('error', 'Unknown error')}")
                    
                # Complete progress bar
                progress_bar.progress(100)
                
                # Reset processing flag
                st.session_state.is_fetching = False
                
            except Exception as e:
                st.session_state.is_fetching = False
                st.error(f"An error occurred: {str(e)}")
                logger.error(f"Error in main process: {str(e)}")

        # Display status messages
        if st.session_state.scan_status:
            with st.expander("Processing Log", expanded=False):
                for msg in st.session_state.scan_status:
                    st.text(msg)

        # Display results
        if st.session_state.scan_complete and st.session_state.current_articles:
            with results_section:
                st.success(f"Found {len(st.session_state.current_articles)} AI articles!")
                if st.session_state.processing_time:
                    st.write(f"Processing time: {st.session_state.processing_time}")

                # Show export options
                st.markdown("### 📊 Export Options")
                export_col1, export_col2, export_col3 = st.columns([1, 1, 1])

                with export_col1:
                    if st.session_state.pdf_data:
                        today_date = datetime.now().strftime("%Y-%m-%d")
                        pdf_filename = f"ai_news_report_{today_date}.pdf"
                        st.download_button(
                            "📄 Download PDF Report",
                            st.session_state.pdf_data,
                            pdf_filename,
                            "application/pdf",
                            use_container_width=True,
                            key="pdf_download"
                        )

                with export_col2:
                    if st.session_state.csv_data:
                        today_date = datetime.now().strftime("%Y-%m-%d")
                        csv_filename = f"ai_news_report_{today_date}.csv"
                        st.download_button(
                            "📊 Download CSV Report",
                            st.session_state.csv_data,
                            csv_filename,
                            "text/csv",
                            use_container_width=True,
                            key="csv_download"
                        )

                with export_col3:
                    if st.session_state.excel_data:
                        today_date = datetime.now().strftime("%Y-%m-%d")
                        excel_filename = f"ai_news_report_{today_date}.xlsx"
                        st.download_button(
                            "📈 Download Excel Report",
                            st.session_state.excel_data,
                            excel_filename,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            key="excel_download"
                        )

                # Show articles
                st.markdown("### Found AI Articles")
                for article in st.session_state.current_articles:
                    st.markdown("---")
                    st.markdown(f"### [{article['title']}]({article['url']})")
                    st.markdown(f"Published: {article['date']}")
                    
                    # Display takeaway
                    takeaway = article.get('takeaway', 'No takeaway available')
                    st.markdown(f"**Key Takeaway:** {takeaway}")
                    
                    # Display key points if available
                    key_points = article.get('key_points', [])
                    if key_points and len(key_points) > 0:
                        st.markdown("**Key Points:**")
                        for point in key_points:
                            st.markdown(f"• {point}")

                    # Assessment summary shown before criteria details
                    assessment = article.get('assessment', 'N/A')
                    score = article.get('assessment_score', 0)
                    render_assessment_box(assessment, score)

                    # Criteria dashboard in a collapsed expander
                    criteria = article.get('criteria_results', [])
                    with st.expander("Criteria Details", expanded=False):
                        render_criteria_dashboard(criteria)

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        logger.error(f"Application error: {str(e)}")

if __name__ == "__main__":
    main()
