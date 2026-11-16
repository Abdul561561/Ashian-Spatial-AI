"""Architectural technology design styles and CSS for Ashian Spatial AI."""

CUSTOM_CSS = """
<style>
    /* Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
    }

    /* Header Banner */
    .hero-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f766e 100%);
        border: 1px solid rgba(45, 212, 191, 0.25);
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    
    .hero-title {
        color: #ffffff;
        font-size: 1.85rem;
        font-weight: 700;
        margin: 0 0 6px 0;
        letter-spacing: -0.5px;
    }

    .hero-subtitle {
        color: #94a3b8;
        font-size: 0.98rem;
        margin: 0;
    }

    /* Metric Cards */
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .metric-card:hover {
        border-color: #14b8a6;
        transform: translateY(-2px);
    }

    .metric-label {
        font-size: 0.80rem;
        font-weight: 600;
        text-transform: uppercase;
        color: #94a3b8;
        letter-spacing: 0.6px;
        margin-bottom: 4px;
    }

    .metric-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
    }

    .metric-sub {
        font-size: 0.75rem;
        color: #2dd4bf;
        margin-top: 4px;
    }

    /* Evidence Box */
    .evidence-box {
        background: #090d16;
        border: 1px solid #1e293b;
        border-left: 4px solid #14b8a6;
        border-radius: 6px;
        padding: 12px 16px;
        margin-top: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #cbd5e1;
    }

    /* Status Badges */
    .badge-validated {
        background-color: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.35);
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    .badge-warning {
        background-color: rgba(234, 179, 8, 0.15);
        color: #facc15;
        border: 1px solid rgba(234, 179, 8, 0.35);
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 600;
    }

    /* Step Navigation Instruction */
    .nav-step,
    .stMarkdown .nav-step,
    div[data-testid="stMarkdownContainer"] .nav-step,
    div[data-testid="stMarkdownContainer"] .nav-step p,
    div[data-testid="stMarkdownContainer"] .nav-step span,
    div[data-testid="stMarkdownContainer"] .nav-step div {
        background-color: #1e293b !important;
        color: #ffffff !important;
    }

    .nav-step {
        background: #1e293b !important;
        color: #ffffff !important;
        border-left: 4px solid #38bdf8 !important;
        padding: 12px 16px !important;
        margin-bottom: 8px !important;
        border-radius: 4px 8px 8px 4px !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        line-height: 1.5 !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15) !important;
    }
    
    .nav-step p {
        color: #ffffff !important;
        margin: 0 !important;
        padding: 0 !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }

    /* Sidebar Branding */
    .sidebar-brand {
        padding: 12px 0 20px 0;
        border-bottom: 1px solid #334155;
        margin-bottom: 16px;
    }
</style>
"""
