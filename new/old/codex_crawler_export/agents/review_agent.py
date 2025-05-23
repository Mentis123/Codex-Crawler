from utils.report_tools import generate_pdf_report, generate_csv_report
import os

class ReviewAgent:
    def __init__(self):
        self.report_dir = "reports"
        os.makedirs(self.report_dir, exist_ok=True)

    def generate_reports(self, selected_articles):
        """
        Generates PDF and CSV reports for selected articles
        """
        pdf_path = os.path.join(self.report_dir, "ai_news_report.pdf")
        csv_path = os.path.join(self.report_dir, "ai_news_report.csv")

        # Generate PDF report
        generate_pdf_report(selected_articles, pdf_path)
        
        # Generate CSV report
        generate_csv_report(selected_articles, csv_path)

        return pdf_path, csv_path
