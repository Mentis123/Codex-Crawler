import streamlit as st
from datetime import datetime, timedelta
from utils.content_extractor import load_source_sites, find_ai_articles, extract_full_content
from utils.ai_analyzer import summarize_article
from utils.ai_analyzer import categorize_article_content
from utils.report_tools import (
    generate_pdf_report,
    generate_csv_report,
    generate_excel_report,
    sort_by_assessment_and_score,
)
from utils.simple_particles import add_simple_particles
from utils.common import calculate_lookback_days
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
        st.session_state.time_value = 1  # Default time period value
        st.session_state.time_unit = "Weeks"  # Default time period unit
        st.session_state.lookback_days = calculate_lookback_days(
            st.session_state.time_value, st.session_state.time_unit
        )
        st.session_state.initialized = True
        st.session_state.last_update = datetime.now()
        st.session_state.scan_complete = False  # Flag to track if a scan has completed
        st.session_state.current_articles = []  # Store articles for persistent access
        logger.info("Session state initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing session state: {str(e)}")
        st.error("Error initializing application. Please refresh the page.")

# Set page config after initialization
st.set_page_config(
    page_title="AI News Aggregator",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# We're using the utils/report_tools.py version instead
from utils.report_tools import generate_pdf_report

# We're using the utils/report_tools.py versions instead
from utils.report_tools import generate_csv_report, generate_excel_report

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

        # Categorize article
        try:
            categorization = categorize_article_content(article['title'], content)
        except Exception as e:
            logger.warning(f"Categorization failed for {article['title']}: {e}")
            categorization = {'category': 'Uncategorized', 'category_justification': 'Error during categorization process.'}
        article_data.update(categorization)

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

        # Ensure settings drawer is hidden while fetching
        if st.session_state.get("is_fetching", False):
            st.session_state.show_settings = False

        # Custom header with settings button
        st.markdown(
            """
            <style>
            .header-container {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 1rem;
            }
            .settings-btn {
                padding: 0.5rem;
                border-radius: 0.375rem;
                background: transparent;
                border: 1px solid rgba(250, 250, 250, 0.2);
                cursor: pointer;
                margin-top: 8px;
            }
            .settings-btn:hover {
                background: rgba(250, 250, 250, 0.1);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        header_col1, header_col2 = st.columns([1, 11])
        with header_col1:
            gear_disabled = st.session_state.get("is_fetching", False)
            if st.button(
                "⚙️",
                key="settings_btn",
                help="Settings",
                type="secondary",
                disabled=gear_disabled,
            ):
                st.session_state.show_settings = not st.session_state.show_settings
        with header_col2:
            st.title("GAI Insights Crocs Monitoring Service")

        from utils.ui_components import render_settings_drawer

        fetch_button, config_saved = render_settings_drawer()
        if config_saved:
            global evaluation_agent
            evaluation_agent = EvaluationAgent()

        # Separate section for displaying results
        results_section = st.container()

        if fetch_button:
            # First hide settings panel
            st.session_state.show_settings = False
            # Close the drawer via query param so it disappears on rerun
            st.query_params["close_settings"] = "1"
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

                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, len(sources))
                    current_batch = sources[start_idx:end_idx]

                    # Calculate cutoff time using unified lookback days
                    days_to_subtract = st.session_state.lookback_days

                    # Create a cutoff_time in the past
                    cutoff_time = (
                        datetime.now().replace(
                            hour=0, minute=0, second=0, microsecond=0
                        )
                        - timedelta(days=days_to_subtract)
                    )
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    logger.info(
                        f"Today is: {current_date}, Lookback: {st.session_state.lookback_days} days, Cutoff: {cutoff_time} (Including articles from {(cutoff_time + timedelta(days=1)).strftime('%Y-%m-%d')} to {current_date})"
                    )

                    # Process current batch
                    for source in current_batch:
                        domain = urlparse(source).netloc or source
                        with st.spinner(f"Researching {domain}..."):
                            batch_articles = process_batch([source], cutoff_time, db, seen_urls, status_placeholder)

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
                    # Show category directly under the date
                    category = article.get('category', 'N/A')
                    category_justification = article.get(
                        'category_justification',
                        'No justification available.'
                    )
                    st.markdown(f"**Category:** {category}")
                    # Get and process the takeaway text
                    import re

                    # Helper function to clean and format takeaway text
                    def clean_takeaway(text):
                        # First, join any stray numbers and letters without adding extra spaces
                        text = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', text)  # Add space between numbers and letters
                        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)  # Add space between letters and numbers

                        # Fix dollar amounts with spaces 
                        text = re.sub(r'\$ *(\d+)', r'$\1', text)  # Remove space after $ sign
                        text = re.sub(r'\$ *(\d+) *\. *(\d+)', r'$\1.\2', text)  # Fix spaced decimal in dollar amounts

                        # Fix numbers with spaces between digits
                        text = re.sub(r'(\d+) +(\d{3})', r'\1,\2', text)  # Convert "200 000" to "200,000"
                        text = re.sub(r'(\d+) *\, *(\d+)', r'\1,\2', text)  # Fix spaced commas
                        text = re.sub(r'(\d+) *\. *(\d+)', r'\1.\2', text)  # Fix spaced decimals

                        # Fix trailing spaces before punctuation
                        text = re.sub(r' +([.,!?:;])', r'\1', text)  # Remove space before punctuation

                        # Fix long run-on words without adding spaces within numbers
                        words = text.split()
                        processed_words = []
                        for word in words:
                            # Don't break numbers or standard patterns
                            if len(word) > 25 and not re.match(r'^[\d.,]+$', word):
                                # Only break very long words
                                chunks = [word[i:i+20] for i in range(0, len(word), 20)]
                                processed_words.append(" ".join(chunks))
                            else:
                                processed_words.append(word)

                        result = " ".join(processed_words)

                        # Final cleanup pass for any remaining issues
                        result = re.sub(r'(\d+) +(\d{3})', r'\1,\2', result)  # Second pass for larger numbers
                        result = re.sub(r' +([.,!?:;])', r'\1', result)  # Final check for spaces before punctuation

                        return result

                    takeaway_text = article.get('takeaway', 'No takeaway available')
                    takeaway_text = clean_takeaway(takeaway_text)

                    # Custom CSS to ensure proper text wrapping
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
                        font-size: 0.9em;
                    }
                    </style>
                    """, unsafe_allow_html=True)

                    st.markdown(
                        f'<div class="takeaway-box"><strong>Takeaway:</strong> {takeaway_text}</div>',
                        unsafe_allow_html=True,
                    )

                    # Assessment box displayed before criteria details
                    assessment = article.get('assessment', 'N/A')
                    score = article.get('assessment_score', 0)
                    render_assessment_box(assessment, score)

                    # Criteria dashboard in a collapsed expander for compact viewing
                    criteria = article.get('criteria_results', [])
                    with st.expander("Criteria Details", expanded=False):
                        render_criteria_dashboard(criteria)
                    st.markdown(f"**Category Justification:** {category_justification}")
        elif st.session_state.scan_complete and not st.session_state.current_articles:
            with results_section:
                st.warning("No articles found. Please try adjusting the time period or check the source sites.")

    except Exception as e:
        st.error("An unexpected error occurred. Please refresh the page.")
        logger.error(f"Critical error: {str(e)}")

if __name__ == "__main__":
    main()