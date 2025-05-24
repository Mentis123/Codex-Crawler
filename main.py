
# Applying the requested UI layout and styling changes, including compact popover and updated help icon.
import streamlit as st
from datetime import datetime, timedelta
from utils.content_extractor import load_source_sites, find_ai_articles, extract_full_content
from utils.ai_analyzer import summarize_article
from utils.report_tools import (
    generate_pdf_report,
    generate_csv_report,
    generate_excel_report,
    sort_by_assessment_and_score,
)
from utils.simple_particles import add_simple_particles
from agents.evaluation_agent import EvaluationAgent
import pandas as pd
import json
import os
from io import BytesIO
import traceback
from openai import OpenAI
from urllib.parse import quote
import logging
import gc
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize evaluation agent
evaluation_agent = EvaluationAgent()

# Set page config before anything else
st.set_page_config(
    page_title="AI News Aggregator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom styles for the new layout
st.markdown("""
    <style>
    .header-container {
        display: flex;
        align-items: center;
        gap: 15px;
        margin-bottom: 20px;
    }
    .settings-panel {
        background: rgba(31, 31, 48, 0.95);
        border: 1px solid rgba(250, 250, 250, 0.2);
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        max-width: 300px;
    }
    .gear-button {
        background: transparent;
        border: none;
        cursor: pointer;
        padding: 5px;
    }
    .stButton button {
        width: 100%;
    }
    .help-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background-color: #4CAF50;
        color: white;
        font-size: 12px;
        cursor: help;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state before anything else
if 'initialized' not in st.session_state:
    try:
        logger.info("Initializing session state")
        st.session_state.articles = []
        st.session_state.selected_articles = []
        st.session_state.scan_status = []
        st.session_state.test_mode = False
        st.session_state.processing_time = None
        st.session_state.processed_urls = set()  # Track processed URLs
        st.session_state.current_batch_index = 0  # Track current batch
        st.session_state.batch_size = 5  # Configurable batch size
        st.session_state.is_fetching = False
        st.session_state.pdf_data = None  # Initialize PDF data
        st.session_state.csv_data = None  # Initialize CSV data
        st.session_state.excel_data = None  # Initialize Excel data
        st.session_state.show_settings = True  # Show settings panel on first load
        st.session_state.show_config = False  # Hide config panel initially
        st.session_state.time_value = 1  # Default time period value
        st.session_state.time_unit = "Weeks"  # Default time period unit
        st.session_state.initialized = True
        st.session_state.last_update = datetime.now()
        st.session_state.scan_complete = False  # Flag to track if a scan has completed
        st.session_state.current_articles = []  # Store articles for persistent access
        logger.info("Session state initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing session state: {str(e)}")
        st.error("Error initializing application. Please refresh the page.")

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
    """Display assessment and score in a colored box."""
    color_map = {"INCLUDE": "#21ba45", "OK": "#f2c037", "CUT": "#db2828"}
    color = color_map.get(assessment, "#cccccc")
    st.markdown(
        f"<div style='border:1px solid {color}; padding:6px 10px; border-radius:4px; display:inline-block; margin-bottom:10px;'>"
        f"<b>Assessment:</b> <span style='color:{color}'>{assessment}</span> &nbsp; "
        f"<b>Score:</b> {score}%"
        "</div>",
        unsafe_allow_html=True,
    )

def process_article(article, source, cutoff_time, db, seen_urls):
    """Process a single article with optimized content extraction and analysis"""
    if article['url'] in seen_urls:
        return None

    try:
        # Extract full content with caching
        content = extract_full_content(article['url'])
        if not content:
            logger.warning(f"No content extracted from {article['url']}")
            return None

        # Generate article takeaway with caching
        try:
            analysis = summarize_article(content)
        except Exception as e:
            logger.warning(f"Takeaway generation failed for {article['title']}: {e}")
            analysis = {'takeaway': 'No takeaway available', 'key_points': []}

        # Create article data
        article_data = {
            'title': article['title'],
            'url': article['url'],
            'date': article['date'],
            'takeaway': analysis.get('takeaway', 'No takeaway available'),
            'source': source,
            'ai_validation': "AI-related article found in scan"
        }

        # Evaluate against selection criteria
        eval_result = evaluation_agent.evaluate_article({
            'title': article['title'],
            'content': content,
            'takeaway': article_data['takeaway']
        })
        article_data.update(eval_result)

        # Save to database if possible
        try:
            db.save_article(article_data)
        except Exception as e:
            logger.error(f"Failed to save article to database: {e}")

        return article_data

    except Exception as e:
        logger.error(f"Error processing article {article['url']}: {str(e)}")
        return None

def process_batch(sources, cutoff_time, db, seen_urls, status_placeholder):
    """Process a batch of sources with parallel article handling and caching"""
    batch_articles = []
    total_article_count = 0

    # Process each source in the batch
    for source in sources:
        try:
            # Skip already processed sources
            if source in st.session_state.processed_urls:
                continue

            # Update status
            current_time = datetime.now().strftime("%H:%M:%S")
            update_status(f"Scanning: {source}")

            # Find AI articles with caching and parallel processing
            try:
                ai_articles = find_ai_articles(source, cutoff_time)
                # Handle tuple return format if present
                if isinstance(ai_articles, tuple):
                    ai_articles = ai_articles[0]
            except Exception as e:
                logger.error(f"Error finding articles from {source}: {e}")
                ai_articles = []

            # Update status if articles found
            if ai_articles:
                update_status(f"Found {len(ai_articles)} AI articles from {source}")
                total_article_count += len(ai_articles)

                # Process articles in parallel when there are multiple
                processed_articles = []
                if len(ai_articles) > 3:
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        # Submit all articles for processing
                        future_to_article = {
                            executor.submit(process_article, article, source, cutoff_time, db, seen_urls): article 
                            for article in ai_articles if article['url'] not in seen_urls
                        }

                        # Process results as they complete
                        for future in as_completed(future_to_article):
                            article_data = future.result()
                            if article_data:
                                processed_articles.append(article_data)
                                seen_urls.add(article_data['url'])
                                update_status(f"Added: {article_data['title']}")
                else:
                    # Process sequentially for small numbers of articles
                    for article in ai_articles:
                        article_data = process_article(article, source, cutoff_time, db, seen_urls)
                        if article_data:
                            processed_articles.append(article_data) 
                            seen_urls.add(article_data['url'])
                            update_status(f"Added: {article_data['title']}")

                # Add successful articles to batch
                batch_articles.extend(processed_articles)

            # Mark source as processed
            st.session_state.processed_urls.add(source)

        except Exception as e:
            logger.error(f"Error processing source {source}: {str(e)}")
            continue

    logger.info(f"Processed {len(sources)} sources, found {total_article_count} articles, added {len(batch_articles)} articles")
    return batch_articles

def main():
    try:
        # Add simple particle effect background
        add_simple_particles()

        # Header with settings toggle
        st.markdown("""
            <style>
            .header-container {
                display: flex;
                align-items: center;
                margin-bottom: 20px;
            }
            .gear-button {
                background: transparent;
                border: none;
                cursor: pointer;
                font-size: 24px;  /* Adjust size as needed */
            }
            </style>
            """, unsafe_allow_html=True)

        header_col1, header_col2 = st.columns([1, 10])

        with header_col1:
            # Conditionally display settings panel
            gear_clicked = st.button("⚙️", key="settings_toggle", help="Toggle Settings")
            if gear_clicked:
                st.session_state.show_settings = not st.session_state.get("show_settings", True)
                st.session_state.show_config = False

        with header_col2:
            st.title("AI News Aggregation System")

        # Settings panel
        if st.session_state.get("show_settings", True):
            with st.container():
                st.markdown('<div class="settings-panel">', unsafe_allow_html=True)

                # Test mode with inline help
                help_text = st.empty()
                test_col1, test_col2 = st.columns([8, 1])
                with test_col1:
                    st.session_state.test_mode = st.toggle(
                        "Test Mode",
                        value=st.session_state.get('test_mode', False),
                        key="test_mode_toggle",
                    )
                with test_col2:
                    st.markdown("""
                        <div class="help-icon" title="In Test Mode, only Wired.com is scanned">?</div>
                    """, unsafe_allow_html=True)

                # Time and Unit inputs
                col1, col2 = st.columns(2)
                with col1:
                    st.number_input(
                        "Time",
                        min_value=1,
                        step=1,
                        format="%d",
                        key="time_value",
                        label_visibility="collapsed"
                    )
                with col2:
                    unit_options = ["Days", "Weeks"]
                    default_index = unit_options.index(st.session_state.get("time_unit", "Weeks"))
                    st.session_state.time_unit = st.selectbox(
                        "Unit",
                        unit_options,
                        index=default_index,
                        key="time_unit_select",
                        label_visibility="collapsed"
                    )

                # Fetch button
                fetch_button = st.button(
                    "Fetch Articles",
                    disabled=st.session_state.is_fetching,
                    type="primary",
                    key="fetch_btn_main",
                    use_container_width=True,
                )
                if fetch_button:
                    st.session_state.show_settings = False
                    st.session_state.show_config = False

                st.markdown('</div>', unsafe_allow_html=True)

            if st.session_state.show_config:
                from utils.config_manager import load_config, save_config
                st.markdown("### Configuration")
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
                cfg_col1, cfg_col2 = st.columns(2)
                with cfg_col1:
                    if st.button("Save Configuration", key="save_config_btn"):
                        global evaluation_agent
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
                        evaluation_agent = EvaluationAgent()
                        st.session_state.show_config = False
                        st.success("Configuration saved.")
                with cfg_col2:
                    if st.button("Close", key="close_config_btn"):
                        st.session_state.show_config = False

        # Separate section for displaying results
        results_section = st.container()

        fetch_button = False
        if gear_clicked:
            fetch_button = False
        else:
            fetch_button = st.session_state.is_fetching

        if fetch_button:
            # First hide settings panel
            st.session_state.show_settings = False
            # Then reset state for a new scan
            st.session_state.is_fetching = True
            st.session_state.pdf_data = None
            st.session_state.csv_data = None
            st.session_state.excel_data = None
            st.session_state.scan_complete = False
            st.session_state.articles = []
            # Force a rerun to immediately hide settings
            st.rerun()

        if fetch_button or st.session_state.is_fetching:
            try:
                start_time = datetime.now()

                sources = load_source_sites(test_mode=st.session_state.test_mode)
                from utils.db_manager import DBManager
                from urllib.parse import urlparse
                db = DBManager()

                seen_urls = set()  # Reset seen URLs each time
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                batch_size = 5
                total_batches = (len(sources) + batch_size - 1) // batch_size

                # Calculate cutoff time once using the selected unit
                if st.session_state.time_unit == "Weeks":
                    days_to_subtract = st.session_state.time_value * 7
                else:
                    days_to_subtract = st.session_state.time_value

                cutoff_time = datetime.now() - timedelta(days=days_to_subtract)
                logger.info(
                    f"Time period: {st.session_state.time_value} {st.session_state.time_unit}, Cutoff: {cutoff_time} (Including articles newer than this date)"
                )

                st.write(
                    f"Scanning articles from the last {st.session_state.time_value} {st.session_state.time_unit.lower()} (since {cutoff_time.strftime('%Y-%m-%d')})"
                )

                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, len(sources))
                    current_batch = sources[start_idx:end_idx]
                    
                    batch_articles = process_batch(current_batch, cutoff_time, db, seen_urls, status_placeholder)
                    
                    # Add articles to session state if found
                    if batch_articles:
                        st.session_state.articles.extend(batch_articles)

                    # Update progress
                    progress = (batch_idx + 1) / total_batches
                    progress_bar.progress(progress)

                # When done, mark the scan as complete
                st.session_state.is_fetching = False
                st.session_state.scan_complete = True

                # Store the current articles for persistent access
                st.session_state.current_articles = sort_by_assessment_and_score(
                    st.session_state.articles.copy()
                )

                # Generate reports and store them in session state
                if st.session_state.articles:
                    st.session_state.pdf_data = generate_pdf_report(st.session_state.current_articles)
                    st.session_state.csv_data = generate_csv_report(st.session_state.current_articles)
                    st.session_state.excel_data = generate_excel_report(st.session_state.current_articles)

                # Show completion message and stats
                end_time = datetime.now()
                elapsed_time = end_time - start_time
                minutes = int(elapsed_time.total_seconds() // 60)
                seconds = elapsed_time.total_seconds() % 60
                st.session_state.processing_time = f"{minutes}m {seconds:.1f}s"

            except Exception as e:
                st.session_state.is_fetching = False
                st.error(f"An error occurred: {str(e)}")
                logger.error(f"Error in main process: {str(e)}")

        # Always display results if we have them (either from current scan or previous one)
        if st.session_state.scan_complete and st.session_state.current_articles:
            with results_section:
                st.success(f"Found {len(st.session_state.current_articles)} AI articles!")
                if st.session_state.processing_time:
                    st.write(f"Processing time: {st.session_state.processing_time}")

                # Always show export options outside of conditional logic to keep them available
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
                            key="pdf_download"  # Unique key to avoid conflicts
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
                            key="csv_download"  # Unique key to avoid conflicts
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
                            key="excel_download"  # Unique key to avoid conflicts
                        )

                # Show articles
                st.markdown("### Found AI Articles")
                for article in st.session_state.current_articles:
                    st.markdown("---")
                    st.markdown(f"### [{article['title']}]({article['url']})")
                    st.markdown(f"Published: {article['date']}")
                    
                    takeaway_text = article.get('takeaway', 'No takeaway available')
                    
                    # Display the takeaway with custom formatting
                    st.subheader("Takeaway")
                    st.markdown("""
                    <style>
                    .takeaway-box {
                        background-color: #1E2530;
                        border-radius: 5px;
                        padding: 15px;
                        margin: 10px 0;
                        color: #FFFFFF;
                        word-wrap: break-word;
                        white-space: normal;
                        max-width: 100%;
                        overflow-wrap: break-word;
                        line-height: 1.5;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="takeaway-box">{takeaway_text}</div>', unsafe_allow_html=True)

                    # Assessment box displayed before criteria details
                    assessment = article.get('assessment', 'N/A')
                    score = article.get('assessment_score', 0)
                    render_assessment_box(assessment, score)

                    # Criteria dashboard in a collapsed expander for compact viewing
                    criteria = article.get('criteria_results', [])
                    with st.expander("Criteria Details", expanded=False):
                        render_criteria_dashboard(criteria)

        elif st.session_state.scan_complete and not st.session_state.current_articles:
            with results_section:
                st.warning("No articles found. Please try adjusting the time period or check the source sites.")

    except Exception as e:
        st.error("An unexpected error occurred. Please refresh the page.")
        logger.error(f"Critical error: {str(e)}")

if __name__ == "__main__":
    main()
