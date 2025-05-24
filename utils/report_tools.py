from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from urllib.parse import unquote
from io import BytesIO
import os
from datetime import datetime
import pandas as pd
from openpyxl.utils import get_column_letter

ASSESSMENT_PRIORITY = {"INCLUDE": 0, "OK": 1, "CUT": 2}


def sort_by_assessment_and_score(articles):
    """Sort articles by assessment category and score."""
    return sorted(
        articles,
        key=lambda a: (
            ASSESSMENT_PRIORITY.get(a.get("assessment", "CUT"), 2),
            -a.get("assessment_score", 0),
        ),
    )

def generate_pdf_report(articles):
    """Generate a detailed PDF report including evaluation info."""
    if not articles:
        return b""

    articles = sort_by_assessment_and_score(articles)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    takeaway_style = ParagraphStyle(
        'TakeawayStyle',
        parent=normal_style,
        leftIndent=20,
        rightIndent=20,
        spaceAfter=12,
        spaceBefore=12,
        borderWidth=1,
        borderColor=colors.lightgrey,
        borderPadding=10,
        borderRadius=5,
        backColor=colors.lightgrey,
    )

    content = []
    today = datetime.now().strftime("%Y-%m-%d")
    content.append(Paragraph(f"AI News Report - {today}", title_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"Top {len(articles)} AI Articles", subtitle_style))
    content.append(Spacer(1, 24))

    for i, article in enumerate(articles, 1):
        title = article.get('title', 'Untitled')
        url = article.get('url', '')
        content.append(Paragraph(f"{i}. <a href='{url}'>{title}</a>", subtitle_style))
        content.append(Spacer(1, 6))

        date = article.get('date', 'Unknown date')
        source = article.get('source', 'Unknown source')
        content.append(Paragraph(f"Published: {date} | Source: {source}", normal_style))
        content.append(Spacer(1, 6))

        takeaway = article.get('takeaway', 'No takeaway available')
        content.append(Paragraph(f"<b>Key Takeaway:</b> {takeaway}", takeaway_style))

        crit_results = article.get('criteria_results', [])
        if crit_results:
            table_data = [["Criteria", "Status", "Notes"]]
            table_styles = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (1, 1), (1, -1), 12),
            ]
            
            for idx, crit in enumerate(crit_results, 1):
                status = "✓" if crit.get('status') else "✗"
                table_data.append([
                    crit.get('criteria', ''),
                    status,
                    crit.get('notes', '')
                ])
                # Add color style for each row's status cell individually
                if crit.get('status'):
                    table_styles.append(('TEXTCOLOR', (1, idx), (1, idx), colors.green))
                else:
                    table_styles.append(('TEXTCOLOR', (1, idx), (1, idx), colors.red))
                    
            table = Table(table_data, colWidths=[2.5 * inch, 0.6 * inch, 3.9 * inch])
            table.setStyle(TableStyle(table_styles))
            content.append(table)
            content.append(Spacer(1, 6))

        assessment = article.get('assessment', 'N/A')
        score = article.get('assessment_score', 0)
        content.append(Paragraph(f"<b>Assessment:</b> {assessment} (Score: {score}%)", normal_style))
        content.append(Spacer(1, 20))

    doc.build(content)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def generate_csv_report(articles):
    """Generate a CSV report including evaluation info."""
    if not articles:
        return b""

    articles = sort_by_assessment_and_score(articles)

    output = BytesIO()
    data = []
    for article in articles:
        url = article.get('url', '')
        if 'file:///' in url:
            url = url.split('https://')[-1]
            url = f'https://{url}'
        url = unquote(url)

        row = {
            'Title': article.get('title', ''),
            'URL': url,
            'Date': article.get('date', ''),
            'Source': article.get('source', ''),
            'Takeaway': article.get('takeaway', ''),
            'Assessment': article.get('assessment', ''),
            'Score': article.get('assessment_score', 0),
        }
        for idx, crit in enumerate(article.get('criteria_results', []), 1):
            row[f'C{idx}'] = 'Y' if crit.get('status') else 'N'
            row[f'C{idx} Notes'] = crit.get('notes', '')
        data.append(row)

    df = pd.DataFrame(data)
    df.to_csv(output, index=False)
    return output.getvalue()

def generate_excel_report(articles):
    """Generate an Excel report including evaluation info."""
    if not articles:
        return b""

    articles = sort_by_assessment_and_score(articles)

    output = BytesIO()
    data = []
    for article in articles:
        url = article.get('url', '')
        if 'file:///' in url:
            url = url.split('https://')[-1]
            url = f'https://{url}'
        url = unquote(url)

        row = {
            'Title': article.get('title', ''),
            'URL': url,
            'Date': article.get('date', ''),
            'Source': article.get('source', ''),
            'Takeaway': article.get('takeaway', ''),
            'Assessment': article.get('assessment', ''),
            'Score': article.get('assessment_score', 0),
        }
        for idx, crit in enumerate(article.get('criteria_results', []), 1):
            row[f'C{idx}'] = 'Y' if crit.get('status') else 'N'
            row[f'C{idx} Notes'] = crit.get('notes', '')
        data.append(row)

    df = pd.DataFrame(data)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='AI News')
        worksheet = writer.sheets['AI News']
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.column_dimensions[get_column_letter(idx + 1)].width = max_length

    return output.getvalue()

def save_reports(pdf_data, csv_data, excel_data, report_dir):
    today_date = datetime.now().strftime("%Y-%m-%d")
    pdf_path = os.path.join(report_dir, f"ai_news_report_{today_date}.pdf")
    csv_path = os.path.join(report_dir, f"ai_news_report_{today_date}.csv")
    excel_path = os.path.join(report_dir, f"ai_news_report_{today_date}.xlsx")

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_data)
    with open(csv_path, "wb") as csv_file:
        csv_file.write(csv_data)
    with open(excel_path, "wb") as excel_file:
        excel_file.write(excel_data)
