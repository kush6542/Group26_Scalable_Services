import subprocess
import os
import sys

def generate_pdf():
    md_file = "docs/FoodFlow_Design_Report.md"
    html_file = "docs/FoodFlow_Design_Report.html"
    pdf_file = "docs/FoodFlow_Design_Report.pdf"

    print("Step 1: Converting Markdown to HTML with Pandoc...")
    css_style = """
    <style>
    @page {
        size: A4;
        margin: 20mm 15mm 20mm 15mm;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 10.5pt;
        line-height: 1.5;
        color: #24292e;
        max-width: 900px;
        margin: 0 auto;
        padding: 20px;
    }
    h1 { font-size: 20pt; border-bottom: 2px solid #eaecef; padding-bottom: 6px; margin-top: 15px; color: #1a202c; }
    h2 { font-size: 15pt; border-bottom: 1px solid #eaecef; padding-bottom: 4px; margin-top: 18px; color: #2d3748; page-break-after: avoid; }
    h3 { font-size: 12pt; margin-top: 14px; color: #4a5568; page-break-after: avoid; }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
        font-size: 9.5pt;
        page-break-inside: avoid;
    }
    th, td {
        border: 1px solid #e2e8f0;
        padding: 6px 10px;
        text-align: left;
    }
    th {
        background-color: #f7fafc;
        font-weight: 600;
        color: #2d3748;
    }
    tr:nth-child(even) {
        background-color: #f8fafc;
    }
    code {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
        font-size: 9pt;
        background-color: #edf2f7;
        padding: 2px 4px;
        border-radius: 3px;
        color: #c53030;
    }
    pre {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 10px;
        overflow-x: auto;
        font-size: 8.5pt;
        page-break-inside: avoid;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        color: #2d3748;
    }
    blockquote {
        margin: 10px 0;
        padding: 0 12px;
        color: #718096;
        border-left: 4px solid #cbd5e0;
    }
    hr {
        height: 1px;
        background-color: #e2e8f0;
        border: none;
        margin: 20px 0;
    }
    .page-break {
        page-break-before: always;
    }
    </style>
    """

    cmd_pandoc = [
        "pandoc",
        md_file,
        "-o", html_file,
        "--standalone",
        "--metadata", "title=FoodFlow: Scalable Microservices Architecture"
    ]
    subprocess.run(cmd_pandoc, check=True)

    # Inject custom styling into HTML
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    html_content = html_content.replace("</head>", f"{css_style}\n</head>")

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[✓] Styled HTML generated at {html_file}")

    print("Step 2: Rendering HTML to PDF using Headless Chrome...")
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        print(f"[ERROR] Chrome not found at {chrome_path}")
        return False

    abs_html = os.path.abspath(html_file)
    abs_pdf = os.path.abspath(pdf_file)

    cmd_chrome = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_pdf}",
        f"file://{abs_html}"
    ]
    subprocess.run(cmd_chrome, check=True)
    print(f"[✓] PDF Report successfully generated at: {abs_pdf}")
    print(f"[✓] File size: {os.path.getsize(abs_pdf) / 1024:.1f} KB")
    return True

if __name__ == "__main__":
    generate_pdf()
