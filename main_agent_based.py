import streamlit as st
from datetime import datetime
import logging
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the new agent-based components
from agents.orchestrator import Orchestrator
from agents.base_agent import BaseAgent
from utils.simple_particles import add_simple_particles

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
                'model': 'gpt-4o-mini'
            },
            'report_config': {
                'max_report_articles': 10
            }
        }
        
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

def main():
    try:
        # Add background effect
        add_simple_particles()

        st.title("AI News Aggregation System")

        # Sidebar controls
        with st.sidebar:
            st.session_state.test_mode = st.toggle(
                "Test Mode",
                value=st.session_state.get('test_mode', False),
                help="In Test Mode, only Wired.com is scanned"
            )

        col1, col2 = st.sidebar.columns([2, 2])
        with col1:
            time_value = st.number_input("Time Period", min_value=1, value=1, step=1)
        with col2:
            time_unit = st.selectbox("Unit", ["Days", "Weeks"], index=1)

        fetch_button = st.sidebar.button(
            "Fetch New Articles",
            disabled=st.session_state.is_fetching,
            type="primary"
        )

        # Create container for results
        results_section = st.container()

        # Clear previous results when starting a new fetch
        if fetch_button:
            st.session_state.is_fetching = True
            st.session_state.pdf_data = None
            st.session_state.csv_data = None
            st.session_state.excel_data = None
            st.session_state.scan_complete = False
            st.session_state.articles = []
            st.session_state.scan_status = []

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
                        time_period=time_value,
                        time_unit=time_unit
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
                        st.session_state.current_articles = st.session_state.selected_articles.copy()
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

                    # Criteria dashboard
                    criteria = article.get('criteria_results', [])
                    if criteria:
                        crit_df = pd.DataFrame([
                            {
                                'Criteria': c.get('criteria'),
                                'Status': '✅' if c.get('status') else '❌',
                                'Notes': c.get('notes')
                            }
                            for c in criteria
                        ])
                        st.table(crit_df)

                    # Assessment summary
                    assessment = article.get('assessment', 'N/A')
                    score = article.get('assessment_score', 0)
                    st.markdown(f"**Assessment:** {assessment} (Score: {score}%)")

    except Exception as e:
        st.error(f"Application error: {str(e)}")
        logger.error(f"Application error: {str(e)}")

if __name__ == "__main__":
    main()