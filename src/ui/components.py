import streamlit as st
import pandas as pd
from typing import Dict, Any, List

def get_stretch_kw() -> Dict[str, Any]:
    """Returns kwargs for responsive element sizing compatible across Streamlit versions."""
    try:
        from packaging import version
        if version.parse(st.__version__) >= version.parse("1.50.0"):
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}

STRETCH_KW = get_stretch_kw()

def render_hero_header():
    """Renders the top branding hero banner."""
    st.markdown("""
    <div class="hero-banner">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 class="hero-title">🏛️ Ashian Spatial AI</h1>
                <p class="hero-subtitle">Architectural Building Understanding & Autonomous Indoor Navigation Platform</p>
            </div>
            <div style="text-align: right;">
                <span class="badge-validated" style="font-size: 0.85rem; padding: 6px 14px; font-weight: 500;">Ground-Truth Factual System</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_kpi_cards(total_plans: int, total_rooms: int, total_doors: int, avg_confidence: float, total_habitable: int = 0):
    """Renders high-level statistical KPI metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Floor Plans</div>
            <div class="metric-value">{total_plans}</div>
            <div class="metric-sub">Architectural Drawings</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        sub_text = f"{total_habitable} Habitable Living Rooms" if total_habitable > 0 else "Extracted Spaces"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Detected Spatial Regions</div>
            <div class="metric-value">{total_rooms}</div>
            <div class="metric-sub">{sub_text}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Doors & Openings</div>
            <div class="metric-value">{total_doors}</div>
            <div class="metric-sub">Navigable Portals</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Extraction Quality</div>
            <div class="metric-value">{avg_confidence:.1f}%</div>
            <div class="metric-sub">Morphological Consistency</div>
        </div>
        """, unsafe_allow_html=True)

def render_evidence_viewer(query_response: Dict[str, Any]):
    """Renders optional technical details for administrators and evaluators (collapsed by default)."""
    with st.expander("🛠️ Technical Details (SQL Query & Database Records)", expanded=False):
        method = query_response.get("generation_method", "")
        model = query_response.get("model_used", "")
        if "RULE" in str(method) or "rule" in str(model):
            engine_label = "Ashian Spatial Engine (Direct Deterministic)"
        else:
            engine_label = f"LLM Inference ({model})"
        
        st.markdown(f"**Execution Engine:** `{engine_label}`")
        
        sql = query_response.get("generated_sql", "")
        if sql:
            st.markdown("**Executed SQL Query:**")
            st.code(sql, language="sql")

        records = query_response.get("records", [])
        if records:
            st.markdown(f"**Database Records ({len(records)} row{'s' if len(records) != 1 else ''}):**")
            df = pd.DataFrame(records)
            st.dataframe(df, **STRETCH_KW)
        else:
            st.caption("No tabular records returned for this query.")
