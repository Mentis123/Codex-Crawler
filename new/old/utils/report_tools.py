from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import csv
from urllib.parse import quote, unquote
from io import BytesIO
import os
from datetime import datetime
import pandas as pd
from openpyxl.utils import get_column_letter

def generate_pdf_report(articles):
    """Generate a PDF report with clean URLs"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        topMargin=0.5*inch,
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch,
        rightMargin=0.5*inch
    )

    styles = getSampleStyleSheet()
    link_style = ParagraphStyle(
        'LinkStyle',
        parent=styles['Normal'],
        textColor=colors.blue,
        underline=True,
        fontSize=8
    )
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )

    table_data = [['Title', 'Date', 'Takeaway']]

    for article in articles:
        url = article['url']
        if 'file:///' in url:
            url = url.replace('file:///', '')
            if 'https://' in url:
                url = url.split('https://', 1)[1]
            elif 'http://' in url:
                url = url.split('http://', 1)[1]
            url = f'https://{url}'
        url = unquote(url)

        title = Paragraph(f'<para><a href="{url}">{article["title"]}</a></para>', link_style)
        date = article['date']
        takeaway = Paragraph(article.get('takeaway', 'No takeaway available'), normal_style)

        table_data.append([title, date, takeaway])

    # Updated column widths to give more space to Takeaway
    table = Table(table_data, colWidths=[3.5*inch, 1*inch, 5.5*inch])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    doc.build([table])
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data

def generate_csv_report(articles):
    """Generate CSV report matching PDF format"""
    output = BytesIO()
    data = []
    for article in articles:
        url = article['url']
        if 'file:///' in url:
            url = url.split('https://')[-1]
            url = f'https://{url}'
        url = unquote(url)

        data.append({
            'Title': article['title'],
            'Date': article['date'],
            'Takeaway': article.get('takeaway', 'No takeaway available')
        })

    df = pd.DataFrame(data)
    df.to_csv(output, index=False, encoding='utf-8')
    return output.getvalue()

def generate_excel_report(articles):
    """Generate Excel report matching PDF format"""
    output = BytesIO()
    data = []
    for article in articles:
        url = article['url']
        if 'file:///' in url:
            url = url.split('https://')[-1]
            url = f'https://{url}'
        url = unquote(url)

        data.append({
            'Title': article['title'],
            'URL': url,
            'Date': article['date'],
            'Takeaway': article.get('takeaway', 'No takeaway available')
        })

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

#Example usage
articles = [
    {'title': 'Article 1', 'date': '2024-10-27', 'url': 'https://example.com/article1', 'takeaway': 'Takeaway 1'},
    {'title': 'Article 2', 'date': '2024-10-26', 'url': 'https://example.com/article2', 'takeaway': 'Takeaway 2'}
]

report_dir = "./reports" #replace with your report directory
os.makedirs(report_dir, exist_ok=True)

pdf_report_data = generate_pdf_report(articles)
csv_report_data = generate_csv_report(articles)
excel_report_data = generate_excel_report(articles)

save_reports(pdf_report_data, csv_report_data, excel_report_data, report_dir)