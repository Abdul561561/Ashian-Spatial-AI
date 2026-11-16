import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OUTPUT_DIR, CLASS_PALETTE
from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.extractor import FloorPlanExtractor
from src.cv_engine.visualizer import FloorPlanVisualizer
from src.database.db_manager import DatabaseManager
from src.spatial_intelligence.graph_builder import SpatialGraphBuilder
from src.spatial_intelligence.navigation import IndoorNavigator
from src.ai_assistant.assistant import AshianSpatialAssistant
from src.ui.styles import CUSTOM_CSS
from src.ui.components import render_hero_header, render_kpi_cards, render_evidence_viewer

def _get_stretch_kw():
    try:
        from packaging import version
        if version.parse(st.__version__) >= version.parse("1.50.0"):
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}

STRETCH_KW = _get_stretch_kw()

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ashian Spatial AI - Building Understanding & Indoor Navigation",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Custom Architectural Theme CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------
# Resource Caching
# ---------------------------------------------------------
@st.cache_resource
def get_database_manager():
    return DatabaseManager()

@st.cache_resource
def get_cv_loader():
    return FloorPlanLoader()

@st.cache_resource
def get_cv_extractor():
    return FloorPlanExtractor()

@st.cache_resource
def get_cv_visualizer():
    return FloorPlanVisualizer()

@st.cache_resource
def get_graph_builder():
    return SpatialGraphBuilder()

@st.cache_resource
def get_indoor_navigator():
    return IndoorNavigator()

db = get_database_manager()
loader = get_cv_loader()
extractor = get_cv_extractor()
visualizer = get_cv_visualizer()
graph_builder = get_graph_builder()
navigator = get_indoor_navigator()

# ---------------------------------------------------------
# Initialize Session State
# ---------------------------------------------------------
# Initialize Session State
# ---------------------------------------------------------
if "current_nav" not in st.session_state:
    st.session_state["current_nav"] = "🏢 Dashboard"
if "selected_plan_id" not in st.session_state:
    st.session_state["selected_plan_id"] = "1"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "assistant" not in st.session_state:
    st.session_state["assistant"] = AshianSpatialAssistant(db_manager=db)

# ---------------------------------------------------------
# Sidebar Navigation & Floor Plan Selection
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <h2 style="color: #2dd4bf; margin: 0; font-size: 1.35rem;">🏛️ Ashian Spatial AI</h2>
        <span style="color: #94a3b8; font-size: 0.80rem;">Building Intelligence Engine v1.0</span>
    </div>
    """, unsafe_allow_html=True)

    nav_options = [
        "🏢 Dashboard",
        "🗺️ Floor Plan Explorer",
        "💬 AI Assistant",
        "🧭 Indoor Navigation",
        "📊 Building Analytics",
        "📑 Extraction Reports",
    ]

    # Handle programmatic tab redirection
    if "nav_redirect" in st.session_state:
        target = st.session_state.pop("nav_redirect")
        if target in nav_options:
            st.session_state["current_nav"] = target
            st.session_state["nav_radio_key"] = target

    # Ensure current_nav is a valid option
    if st.session_state["current_nav"] not in nav_options:
        st.session_state["current_nav"] = nav_options[0]

    # Initialize nav_radio_key in session state if missing
    if "nav_radio_key" not in st.session_state or st.session_state["nav_radio_key"] not in nav_options:
        st.session_state["nav_radio_key"] = st.session_state["current_nav"]

    def on_nav_change():
        st.session_state["current_nav"] = st.session_state["nav_radio_key"]

    nav_choice = st.radio(
        "Navigation",
        nav_options,
        index=nav_options.index(st.session_state["current_nav"]),
        key="nav_radio_key",
        on_change=on_nav_change,
    )
    # Ensure nav_choice is strictly tied to current_nav
    nav_choice = st.session_state["current_nav"]

    st.markdown("---")
    st.markdown("### 📐 Floor Plan Selection")
    
    # Load all available floor plans from DB
    plans_df = db.get_all_floor_plans()
    
    if not plans_df.empty:
        plan_options = plans_df["plan_id"].tolist()
        if st.session_state["selected_plan_id"] not in plan_options:
            st.session_state["selected_plan_id"] = plan_options[0]

        def on_plan_change():
            st.session_state["selected_plan_id"] = st.session_state["plan_select_key"]

        plan_idx = plan_options.index(st.session_state["selected_plan_id"])
        st.selectbox(
            "Select Floor Plan ID",
            options=plan_options,
            index=plan_idx,
            key="plan_select_key",
            on_change=on_plan_change,
            help="Select an architectural floor plan from the Kaggle dataset."
        )
        active_plan_id = st.session_state["selected_plan_id"]
    else:
        st.warning("No floor plans in database. Please run dataset population.")
        active_plan_id = "1"

    st.markdown("---")
    st.markdown("### ⚡ System Status")
    st.markdown(f"**Active Plan:** `Plan #{active_plan_id}`")
    st.markdown(f"**Indexed Drawings:** `{len(plans_df)} plans`")
    st.markdown("**Assistant Mode:** `Factual Grounded`")

    st.markdown("""
    <div style="font-size: 0.72rem; color: #64748b; margin-top: 15px;">
        Ashian Spatial AI Architectural Platform<br>
        OpenCV, NetworkX, SQLite & Spatial Intelligence
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# Helper: Load active plan data
# ---------------------------------------------------------
def load_active_data(pid: str):
    plan_meta = db.get_floor_plan(pid)
    rooms_df = db.get_rooms_df(pid)
    doors_df = db.get_doors_df(pid)
    windows_df = db.get_windows_df(pid)
    conns_df = db.get_connections_df(pid)
    metadata = db.get_metadata(pid)

    # Load original image and mask
    try:
        img_rgb, mask_rgb, _ = loader.load_pair(pid)
    except Exception:
        img_rgb, mask_rgb = None, None

    # Load / compute extracted structures for visualizer
    if mask_rgb is not None:
        extracted = extractor.extract_all(mask_rgb, plan_id=pid)
    else:
        extracted = None

    # Clean room types for clean user display
    if not rooms_df.empty:
        rooms_df = rooms_df.copy()
        rooms_df["room_type"] = rooms_df["room_type"].astype(str).str.replace(r"\s*\[(Heuristic|Service|Outdoor|Circulation)\]", "", regex=True)

    # Build NetworkX graph using high-fidelity connections
    conns_to_use = extracted["connections"] if (extracted and extracted.get("connections")) else conns_df
    conns_df_clean = conns_to_use if isinstance(conns_to_use, pd.DataFrame) else pd.DataFrame(conns_to_use)
    G = graph_builder.build_graph(rooms_df, conns_df_clean, doors_df)

    return {
        "plan_meta": plan_meta,
        "rooms_df": rooms_df,
        "doors_df": doors_df,
        "windows_df": windows_df,
        "conns_df": conns_df_clean,
        "metadata": metadata,
        "img_rgb": img_rgb,
        "mask_rgb": mask_rgb,
        "extracted": extracted,
        "graph": G,
    }

# =========================================================
# SECTION 1: DASHBOARD
# =========================================================
if nav_choice == "🏢 Dashboard":
    render_hero_header()

    # KPI Statistics
    total_plans = len(plans_df)
    total_rooms = int(plans_df["num_rooms"].sum()) if "num_rooms" in plans_df.columns else 0
    total_habitable = int(plans_df["num_habitable_rooms"].sum()) if "num_habitable_rooms" in plans_df.columns else 0
    total_doors = int(plans_df["num_doors"].sum()) if "num_doors" in plans_df.columns else 0
    avg_conf = float(plans_df["extraction_confidence_score"].mean()) if "extraction_confidence_score" in plans_df.columns else 0.0

    render_kpi_cards(total_plans, total_rooms, total_doors, avg_conf, total_habitable)

    st.markdown("<br>", unsafe_allow_html=True)

    # Architectural Overview & Highlights
    col_left, col_right = st.columns([1.6, 1.0])

    with col_left:
        st.markdown("### 📋 Indexed Architectural Floor Plans")
        if not plans_df.empty:
            cols_to_show = ["plan_id", "width", "height", "aspect_ratio"]
            rename_map = {
                "plan_id": "Plan ID",
                "width": "Width (px)",
                "height": "Height (px)",
                "aspect_ratio": "Ratio",
                "num_habitable_rooms": "Habitable Rooms",
                "num_rooms": "Detected Regions",
                "num_doors": "Doors",
                "num_windows": "Windows",
                "num_connections": "Connections",
                "extraction_confidence_score": "Confidence (%)",
                "validation_status": "Status"
            }
            if "num_habitable_rooms" in plans_df.columns:
                cols_to_show.append("num_habitable_rooms")
            cols_to_show.extend(["num_rooms", "num_doors", "num_windows", "num_connections", "extraction_confidence_score", "validation_status"])
            display_df = plans_df[[c for c in cols_to_show if c in plans_df.columns]].rename(columns=rename_map)
            st.dataframe(display_df, **STRETCH_KW, height=360)
        else:
            st.info("No floor plans loaded yet.")

    with col_right:
        st.markdown("### ⚙️ Architectural AI Pipeline")
        st.markdown("""
        1. **Dataset Ingestion**: Pairs original CAD drawings with CVC-FP multi-class segmentation masks.
        2. **CV Engine**: Segment interior rooms, door openings, facade windows, and structural partitions.
        3. **Spatial SQLite**: Stores precise bounding boxes, centroids, topological links, and pixel areas.
        4. **Topological Intelligence**: Builds a NetworkX room-connectivity graph for autonomous indoor pathfinding.
        5. **Evidence-Backed QA**: OpenRouter LLM translates natural language queries to strictly read-only SQL queries.
        """)

        st.info("💡 **Zero-Hallucination Protocol:** Scale calibration is absent in Kaggle floor plan annotations. All spatial metrics are reported strictly in pixels (px).")

    def navigate_to(target_section: str):
        st.session_state["current_nav"] = target_section
        st.session_state["nav_radio_key"] = target_section

    # Quick Access Buttons
    st.markdown("### 🚀 Quick Actions")
    qcol1, qcol2, qcol3 = st.columns(3)
    with qcol1:
        st.button("🗺️ Open Floor Plan Explorer", **STRETCH_KW, on_click=navigate_to, args=("🗺️ Floor Plan Explorer",))
    with qcol2:
        st.button("💬 Ask AI Assistant", **STRETCH_KW, on_click=navigate_to, args=("💬 AI Assistant",))
    with qcol3:
        st.button("🧭 Plan Indoor Route", **STRETCH_KW, on_click=navigate_to, args=("🧭 Indoor Navigation",))

# =========================================================
# SECTION 2: FLOOR PLAN EXPLORER
# =========================================================
elif nav_choice == "🗺️ Floor Plan Explorer":
    data = load_active_data(active_plan_id)
    
    st.markdown(f"## 🗺️ Floor Plan Explorer – Plan #{active_plan_id}")

    if data["plan_meta"]:
        pm = data["plan_meta"]
        st.caption(f"Dimensions: {pm['width']} × {pm['height']} px | Aspect Ratio: {pm['aspect_ratio']} | Indoor Pixels: {pm['indoor_pixels']:,} px ({pm['indoor_percentage']}%)")

    if data["metadata"] and data["metadata"].get("room_count_breakdown"):
        st.info(f"🏛️ **Spatial Region Audit**: {data['metadata']['room_count_breakdown']}")

    # Multi-tab visual inspection
    tab_overlay, tab_orig, tab_mask, tab_rooms, tab_doors = st.tabs([
        "🎨 Multi-Class Visual Overlay",
        "📄 Original CAD Drawing",
        "🎭 Segmentation Mask",
        "🚪 Extracted Rooms Data",
        "🚪 Doors & Windows",
    ])

    with tab_overlay:
        col_img, col_inspect = st.columns([2.0, 1.0])
        
        # Interactive room highlight selector
        rooms_df = data["rooms_df"]
        room_options = ["None (Show All Rooms)"]
        if not rooms_df.empty:
            for _, r in rooms_df.iterrows():
                room_options.append(f"Room {r['room_index']}: {r['room_type']} ({r['pixel_area']:,} px)")

        with col_inspect:
            st.markdown("#### 🎯 Interactive Room Highlighting")
            selected_room_str = st.selectbox("Highlight Room", room_options, index=0)
            
            highlight_id = None
            if selected_room_str != "None (Show All Rooms)":
                highlight_id = int(selected_room_str.split(":")[0].replace("Room", "").strip())

            show_doors_flag = st.checkbox("Show Door Markers", value=True)
            show_windows_flag = st.checkbox("Show Window Openings", value=True)
            show_labels_flag = st.checkbox("Show Room Badges", value=True)

            if highlight_id is not None and not rooms_df.empty:
                sel_row = rooms_df[rooms_df["room_index"] == highlight_id].iloc[0]
                clean_t = str(sel_row['room_type']).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
                win_cnt = sel_row.get('window_count', 0)
                st.markdown("---")
                st.markdown(f"### 📍 Room {highlight_id}: {clean_t}")
                st.markdown(f"**Classification:** `{clean_t}`")
                st.markdown(f"**Pixel Area:** `{sel_row['pixel_area']:,} px`")
                st.markdown(f"**Adjacent Windows:** `{win_cnt} window(s)`")
                st.markdown(f"**Centroid:** `({sel_row['centroid_x']}, {sel_row['centroid_y']})`")
                st.markdown(f"**Bounding Box:** `({sel_row['bbox_x']}, {sel_row['bbox_y']}, {sel_row['bbox_w']}×{sel_row['bbox_h']})`")
                
                with st.expander("🔬 Advanced Geometric Properties", expanded=False):
                    sem_class = sel_row.get('semantic_class', sel_row.get('raw_class', 'Room'))
                    inf_type = sel_row.get('inferred_type', sel_row['room_type'])
                    st.markdown(f"**Semantic Class:** `{sem_class}`")
                    st.markdown(f"**Inferred Typology:** `{inf_type}`")
                    st.markdown(f"**Aspect Ratio:** `{sel_row['aspect_ratio']}`")
                    st.markdown(f"**Solidity:** `{sel_row['solidity']}`")
                    st.markdown(f"**Shape Consistency:** `{sel_row['confidence'] * 100:.0f}%`")

        with col_img:
            if data["img_rgb"] is not None and data["extracted"] is not None:
                overlay = visualizer.create_overlay(
                    data["img_rgb"],
                    data["extracted"],
                    alpha=0.40,
                    highlight_room_id=highlight_id,
                    show_doors=show_doors_flag,
                    show_windows=show_windows_flag,
                    show_labels=show_labels_flag,
                )
                st.image(overlay, caption=f"Floor Plan #{active_plan_id} Annotated Overlay", **STRETCH_KW)
            else:
                st.warning("Floor plan image could not be loaded.")

    with tab_orig:
        if data["img_rgb"] is not None:
            st.image(data["img_rgb"], caption=f"Original CAD Floor Plan #{active_plan_id}", **STRETCH_KW)
        else:
            st.warning("Original CAD drawing not available.")

    with tab_mask:
        col_m1, col_m2 = st.columns([2.0, 1.0])
        with col_m1:
            if data["mask_rgb"] is not None:
                st.image(data["mask_rgb"], caption=f"Raw CVC-FP Semantic Mask #{active_plan_id}", **STRETCH_KW)
        with col_m2:
            st.markdown("#### 🎨 Mask Color Legend")
            for cls_name, info in CLASS_PALETTE.items():
                st.markdown(f"""
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <span style="display: inline-block; width: 20px; height: 20px; background-color: {info['hex']}; border-radius: 4px; margin-right: 10px; border: 1px solid #ffffff33;"></span>
                    <span><strong>{cls_name.replace('_', ' ').title()}:</strong> <span style="color: #94a3b8; font-size: 0.82rem;">{info['description']}</span></span>
                </div>
                """, unsafe_allow_html=True)

    with tab_rooms:
        if not data["rooms_df"].empty:
            rdf = data["rooms_df"]
            n_hab = int(rdf["is_habitable_room"].sum()) if "is_habitable_room" in rdf.columns else len(rdf)
            st.markdown(f"### 🚪 Extracted Spatial Regions ({len(rdf)} Total Regions | {n_hab} Habitable Rooms)")
            st.dataframe(rdf, **STRETCH_KW)
            csv = rdf.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Rooms CSV", csv, f"plan_{active_plan_id}_rooms.csv", "text/csv")
        else:
            st.info("No rooms extracted for this plan.")

    with tab_doors:
        c_d, c_w = st.columns(2)
        with c_d:
            st.markdown("### 🚪 Doors & Portals")
            if not data["doors_df"].empty:
                st.dataframe(data["doors_df"], **STRETCH_KW)
            else:
                st.info("No doors detected.")
        with c_w:
            st.markdown("### 🪟 Exterior Windows")
            if not data["windows_df"].empty:
                st.dataframe(data["windows_df"], **STRETCH_KW)
            else:
                st.info("No windows detected.")

# =========================================================
# SECTION 3: AI ASSISTANT
# =========================================================
elif nav_choice == "💬 AI Assistant":
    col_head, col_clear = st.columns([3, 1])
    with col_head:
        st.markdown("## 💬 AI Architectural Assistant")
        st.caption(f"Factual architectural assistant answering questions for Floor Plan #{active_plan_id}. Grounded strictly in validated database records.")
    with col_clear:
        if st.session_state.chat_history:
            if st.button("🗑️ Clear Conversation", **STRETCH_KW):
                st.session_state.chat_history = []
                st.session_state.assistant.clear_history()
                st.rerun()

    # Suggested Questions
    st.markdown("##### 💡 Suggested Questions:")
    cols = st.columns(3)
    presets = [
        "How many rooms are in this floor plan?",
        "What is the largest room by area?",
        "What rooms connect to Room 1?",
        "How many doors and windows were detected?",
        "Which rooms have no exterior windows?",
        "What is the total room area in this plan?",
    ]

    selected_prompt = None
    for i, p in enumerate(presets):
        c = cols[i % 3]
        if c.button(p, key=f"btn_preset_{i}", **STRETCH_KW):
            selected_prompt = p

    # Chat Input Box
    user_query = st.chat_input(f"Ask a question about Floor Plan #{active_plan_id} (e.g. What rooms connect to Room 1?)...")
    
    query_to_run = user_query or selected_prompt

    if query_to_run:
        # Run QA pipeline with spinner loading indicator
        with st.spinner("Analyzing architectural database..."):
            response = st.session_state.assistant.ask(query_to_run, active_plan_id=active_plan_id)
            st.session_state.chat_history.append(response)

    # Render Chat History
    st.markdown("---")
    if st.session_state.chat_history:
        for item in st.session_state.chat_history:
            with st.chat_message("user"):
                st.markdown(item["question"])

            with st.chat_message("assistant"):
                st.markdown(item["answer"])
                
                # Collapsed Technical Details for evaluators and administrators
                render_evidence_viewer(item)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 36px 20px; color: #94a3b8; background: #1e293b; border-radius: 10px; border: 1px dashed #334155; margin-top: 15px;">
            <span style="font-size: 2.2rem;">🏛️</span>
            <h4 style="color: #f1f5f9; margin: 10px 0 5px 0;">Welcome to Ashian Spatial AI Assistant</h4>
            <p style="font-size: 0.90rem; max-width: 520px; margin: 0 auto; color: #cbd5e1;">Select one of the suggested questions above or enter a question in the chat input below to analyze rooms, doors, windows, and spatial metrics.</p>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# SECTION 4: INDOOR NAVIGATION
# =========================================================
elif nav_choice == "🧭 Indoor Navigation":
    data = load_active_data(active_plan_id)
    G = data["graph"]
    rooms_df = data["rooms_df"]

    st.markdown(f"## 🧭 Indoor Navigation & Pathfinding – Plan #{active_plan_id}")

    # Graph Topology Summary
    metrics = graph_builder.get_graph_metrics(G)
    status_str = "Fully Connected" if metrics['is_fully_connected'] else "Partitioned Sectors"
    st.caption(
        f"Navigation Network: {metrics['num_rooms']} Rooms | "
        f"{metrics['num_connections']} Accessible Passages | "
        f"Network State: {status_str}"
    )

    if rooms_df.empty or len(rooms_df) < 2:
        st.info("Insufficient rooms extracted to compute navigation paths.")
    else:
        # Check if plan has verified door connections
        num_detected_doors = len(data["doors_df"]) if not data["doors_df"].empty else 0
        if metrics["num_connections"] == 0:
            st.info(
                f"ℹ️ **Floor Plan #{active_plan_id}** does not contain annotated interior door connections in the dataset. "
                "To explore active indoor navigation with Dijkstra routing and step-by-step guidance, select **Plan 1, Plan 5, Plan 10, Plan 11, or Plan 12** from the sidebar."
            )

        col_ctrl, col_map = st.columns([1.1, 1.9])

        with col_ctrl:
            st.markdown("### 📍 Route Planner")
            room_choices = [int(r["room_index"]) for _, r in rooms_df.iterrows()]
            room_labels = {}
            for _, r in rooms_df.iterrows():
                clean_t = str(r["room_type"]).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
                room_labels[int(r["room_index"])] = f"Room {r['room_index']}: {clean_t}"

            src_room = st.selectbox(
                "Source Room",
                options=room_choices,
                format_func=lambda x: room_labels.get(x, f"Room {x}"),
                index=0,
                key="nav_src_room_select",
            )

            tgt_room = st.selectbox(
                "Destination Room",
                options=room_choices,
                format_func=lambda x: room_labels.get(x, f"Room {x}"),
                index=min(1, len(room_choices) - 1),
                key="nav_tgt_room_select",
            )

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                find_route_btn = st.button("🚀 Calculate Route", **STRETCH_KW)
            with col_btn2:
                entrance_btn = st.button("🚪 From Main Entrance", **STRETCH_KW)

            nav_result = None
            if entrance_btn:
                nav_result = navigator.navigate_from_entrance(G, tgt_room)
                st.session_state["nav_last_mode"] = ("entrance", active_plan_id, tgt_room)
                st.session_state["last_nav_result"] = nav_result
            elif find_route_btn:
                nav_result = navigator.navigate(G, src_room, tgt_room)
                st.session_state["nav_last_mode"] = ("route", active_plan_id, src_room, tgt_room)
                st.session_state["last_nav_result"] = nav_result
            elif st.session_state.get("nav_last_mode") == ("entrance", active_plan_id, tgt_room):
                nav_result = st.session_state.get("last_nav_result")
            else:
                nav_result = navigator.navigate(G, src_room, tgt_room)
                st.session_state["nav_last_mode"] = ("route", active_plan_id, src_room, tgt_room)
                st.session_state["last_nav_result"] = nav_result

            # Display Turn-by-Turn Guidance
            if nav_result:
                st.markdown("---")
                is_success = bool(nav_result.get("success", False))
                num_steps = int(nav_result.get("num_steps", 0))
                total_dist = float(nav_result.get("total_distance_px", nav_result.get("total_distance", 0.0)))
                instructions = nav_result.get("instructions", [])

                if is_success:
                    if src_room == tgt_room and not (st.session_state.get("nav_last_mode") and st.session_state["nav_last_mode"][0] == "entrance"):
                        st.info(f"ℹ️ {nav_result.get('message', 'Source and destination are both the same room. No movement required.')}")
                    else:
                        st.success(f"Route Calculated: {num_steps} Step{'s' if num_steps != 1 else ''} | Total Distance: {total_dist:,.1f} px")

                    if instructions:
                        st.markdown("#### 🚶 Step-by-Step Guidance:")
                        for step in instructions:
                            st.markdown(
                                f'<div class="nav-step" style="background-color: #1e293b !important; color: #ffffff !important; '
                                f'border-left: 4px solid #38bdf8 !important; padding: 12px 16px !important; margin-bottom: 8px !important; '
                                f'border-radius: 4px 8px 8px 4px !important; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15) !important;">'
                                f'<p style="color: #ffffff !important; font-size: 0.95rem !important; font-weight: 500 !important; '
                                f'line-height: 1.5 !important; margin: 0 !important; padding: 0 !important;">{step}</p>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                else:
                    err_msg = nav_result.get("error") or nav_result.get("message") or f"No continuous path connects Room {src_room} and Room {tgt_room}."
                    st.warning(f"⚠️ {err_msg}")

        with col_map:
            st.markdown("### 🗺️ Visual Route Overlay")
            if data["img_rgb"] is not None and data["extracted"] is not None:
                # Render base visual overlay
                base_overlay = visualizer.create_overlay(
                    data["img_rgb"],
                    data["extracted"],
                    alpha=0.35,
                    show_doors=True,
                    show_windows=True,
                    show_labels=True,
                )

                # Draw navigation path if available
                if nav_result and nav_result.get("success", False) and nav_result.get("waypoints"):
                    waypoints = nav_result["waypoints"]
                    room_names = [r.get("name", "") for r in nav_result.get("path_rooms", []) if isinstance(r, dict)]
                    route_overlay = visualizer.draw_navigation_route(base_overlay, waypoints, room_names)
                    caption_text = f"Navigation Route ({src_room} ➔ {tgt_room})" if src_room != tgt_room else f"Room {src_room} Location"
                    st.image(route_overlay, caption=caption_text, **STRETCH_KW)
                else:
                    st.image(base_overlay, caption="Floor Plan Topological Layout", **STRETCH_KW)
            else:
                st.warning("Floor plan visual overlay could not be rendered.")

# =========================================================
# SECTION 5: BUILDING ANALYTICS
# =========================================================
elif nav_choice == "📊 Building Analytics":
    data = load_active_data(active_plan_id)
    rooms_df = data["rooms_df"]

    st.markdown(f"## 📊 Building Spatial Analytics – Plan #{active_plan_id}")

    if data["metadata"] and data["metadata"].get("room_count_breakdown"):
        st.caption(f"Spatial Classification: {data['metadata']['room_count_breakdown']}")

    if not rooms_df.empty:
        col_a1, col_a2 = st.columns(2)

        with col_a1:
            st.markdown("### 📐 Room Area Distribution")
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#1e293b')
            
            bars = ax.bar(
                [f"R{r}" for r in rooms_df["room_index"]],
                rooms_df["pixel_area"],
                color="#2dd4bf",
                edgecolor="#14b8a6",
            )
            ax.set_xlabel("Room Index", color="#cbd5e1")
            ax.set_ylabel("Pixel Area (px)", color="#cbd5e1")
            ax.tick_params(colors="#94a3b8")
            plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)
            ax.grid(color="#334155", linestyle="--", alpha=0.5)
            for spine in ax.spines.values():
                spine.set_color("#475569")
            fig.tight_layout()
            st.pyplot(fig)

        with col_a2:
            st.markdown("### 🏠 Room Functional Typology Breakdown")
            # Clean typology labels
            clean_types = rooms_df["room_type"].astype(str).str.replace(r"\s*\[(Heuristic|Service|Outdoor|Circulation)\]", "", regex=True)
            type_counts = clean_types.value_counts()
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            fig2.patch.set_facecolor('#0f172a')
            ax2.set_facecolor('#1e293b')
            
            colors = ["#2dd4bf", "#38bdf8", "#f59e0b", "#ec4899", "#a855f7", "#64748b"]
            wedges, texts, autotexts = ax2.pie(
                type_counts.values,
                labels=type_counts.index,
                autopct="%1.1f%%",
                colors=colors[:len(type_counts)],
                textprops={'color': "#f1f5f9"},
            )
            for at in autotexts:
                at.set_color("#0f172a")
                at.set_weight("bold")
            st.pyplot(fig2)

        st.markdown("---")
        st.markdown("### 📈 Room Compactness & Aspect Ratio Analysis")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            fig3, ax3 = plt.subplots(figsize=(6, 3.5))
            fig3.patch.set_facecolor('#0f172a')
            ax3.set_facecolor('#1e293b')
            ax3.scatter(rooms_df["aspect_ratio"], rooms_df["solidity"], color="#38bdf8", s=80, edgecolors="#ffffff", alpha=0.85)
            ax3.set_xlabel("Aspect Ratio (Width / Height)", color="#cbd5e1")
            ax3.set_ylabel("Solidity (Convexity)", color="#cbd5e1")
            ax3.tick_params(colors="#94a3b8")
            ax3.grid(color="#334155", linestyle="--", alpha=0.5)
            for spine in ax3.spines.values():
                spine.set_color("#475569")
            st.pyplot(fig3)

        with col_s2:
            st.markdown("#### 📊 Spatial Statistics Summary")
            st.markdown(f"**Total Rooms:** `{len(rooms_df)}`")
            st.markdown(f"**Mean Room Area:** `{int(rooms_df['pixel_area'].mean()):,} px`")
            st.markdown(f"**Median Room Area:** `{int(rooms_df['pixel_area'].median()):,} px`")
            st.markdown(f"**Largest Room:** `{rooms_df.loc[rooms_df['pixel_area'].idxmax(), 'room_name']} ({rooms_df['pixel_area'].max():,} px)`")
            st.markdown(f"**Smallest Room:** `{rooms_df.loc[rooms_df['pixel_area'].idxmin(), 'room_name']} ({rooms_df['pixel_area'].min():,} px)`")
            st.markdown(f"**Average Quality Index:** `{rooms_df['confidence'].mean() * 100:.1f}%`")
    else:
        st.info("No room data available for analytics.")

# =========================================================
# SECTION 6: EXTRACTION REPORTS
# =========================================================
elif nav_choice == "📑 Extraction Reports":
    data = load_active_data(active_plan_id)
    meta = data["metadata"]
    rooms_df = data["rooms_df"]
    doors_df = data["doors_df"]
    windows_df = data["windows_df"]
    G = data["graph"]

    st.markdown(f"## 📑 Architectural Extraction Report – Plan #{active_plan_id}")
    st.caption("Computer-vision extracted spatial inventory, room categories, structural elements, and topological connectivity.")

    if meta:
        tot_regions = meta.get("total_detected_regions", meta.get("num_rooms", len(rooms_df)))
        num_hab = meta.get("num_habitable_rooms", 0)
        num_serv = meta.get("num_service_rooms", 0)
        num_corr = meta.get("num_corridors", 0)
        num_balc = meta.get("num_balconies", 0)
        num_doors = meta.get("num_doors", len(doors_df))
        num_windows = meta.get("num_windows", len(windows_df))
        num_walls = meta.get("num_walls", 0)
        cov_pct = meta.get("room_indoor_coverage_pct", 0.0)
        num_conns = meta.get("num_connections", G.number_of_edges())
        import networkx as nx
        is_conn = nx.is_connected(G) if G.number_of_nodes() > 0 else False
        conn_status = "Fully Connected" if is_conn and num_conns > 0 else ("Partially Connected" if num_conns > 0 else "Disconnected / No Doors")

        # Row 1 Metric Cards: Spatial Regions
        st.markdown("### 📊 Spatial Regions & Living Areas")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Total Regions", f"{tot_regions}")
        with c2:
            st.metric("Habitable Living", f"{num_hab}")
        with c3:
            st.metric("Service Spaces", f"{num_serv}")
        with c4:
            st.metric("Corridors", f"{num_corr}")
        with c5:
            st.metric("Balconies / Sills", f"{num_balc}")

        # Row 2 Metric Cards: Elements & Structure
        st.markdown("### 🚪 Openings & Physical Structure")
        c6, c7, c8, c9, c10 = st.columns(5)
        with c6:
            st.metric("Doors & Portals", f"{num_doors}")
        with c7:
            st.metric("Exterior Windows", f"{num_windows}")
        with c8:
            st.metric("Structural Walls", f"{num_walls}")
        with c9:
            st.metric("Indoor Coverage", f"{cov_pct:.1f}%")
        with c10:
            st.metric("Connectivity", conn_status)

        st.markdown("---")

        # Visual Composition & Inventory Charts
        col_ch1, col_ch2 = st.columns(2)
        with col_ch1:
            st.markdown("#### 🏠 Spatial Typology Composition")
            labels = ["Habitable", "Service", "Corridor", "Balcony / Sill"]
            vals = [num_hab, num_serv, num_corr, num_balc]
            non_zero = [(l, v) for l, v in zip(labels, vals) if v > 0]
            if non_zero:
                nz_labels, nz_vals = zip(*non_zero)
                fig_pie, ax_pie = plt.subplots(figsize=(5, 3.5))
                fig_pie.patch.set_facecolor('#0f172a')
                ax_pie.set_facecolor('#0f172a')
                palette = ["#2dd4bf", "#38bdf8", "#f59e0b", "#ec4899"]
                wedges, texts, autotexts = ax_pie.pie(
                    nz_vals,
                    labels=nz_labels,
                    autopct="%1.0f%%",
                    colors=palette[:len(nz_vals)],
                    textprops={'color': "#f1f5f9", 'fontsize': 9},
                    startangle=140
                )
                for at in autotexts:
                    at.set_color("#0f172a")
                    at.set_weight("bold")
                fig_pie.tight_layout()
                st.pyplot(fig_pie)
            else:
                st.info("No spatial region distribution data available.")

        with col_ch2:
            st.markdown("#### 🏛️ Architectural Element Inventory")
            fig_bar, ax_bar = plt.subplots(figsize=(5, 3.5))
            fig_bar.patch.set_facecolor('#0f172a')
            ax_bar.set_facecolor('#1e293b')
            elems = ["Regions", "Doors", "Windows", "Walls"]
            counts = [tot_regions, num_doors, num_windows, num_walls]
            ax_bar.bar(elems, counts, color=["#2dd4bf", "#38bdf8", "#f59e0b", "#a855f7"], width=0.55)
            ax_bar.set_ylabel("Count", color="#cbd5e1", fontsize=9)
            ax_bar.tick_params(colors="#94a3b8")
            ax_bar.grid(color="#334155", linestyle="--", alpha=0.4, axis="y")
            for spine in ax_bar.spines.values():
                spine.set_color("#475569")
            fig_bar.tight_layout()
            st.pyplot(fig_bar)

        st.markdown("---")

        # Structured Architectural Inventory Table
        st.markdown("### 📋 Structured Architectural Inventory")
        inventory_data = [
            {"Category": "Primary Habitable Rooms", "Description": "Living Room, Bedrooms, Dining", "Count": num_hab, "Share": f"{(num_hab/tot_regions*100):.1f}%" if tot_regions else "N/A"},
            {"Category": "Circulation Corridors", "Description": "Hallways, Circulation Spines", "Count": num_corr, "Share": f"{(num_corr/tot_regions*100):.1f}%" if tot_regions else "N/A"},
            {"Category": "Service Spaces", "Description": "Bathrooms, Restrooms, Utilities", "Count": num_serv, "Share": f"{(num_serv/tot_regions*100):.1f}%" if tot_regions else "N/A"},
            {"Category": "Exterior Balconies / Terraces", "Description": "Balconies, Exterior Access, Sills", "Count": num_balc, "Share": f"{(num_balc/tot_regions*100):.1f}%" if tot_regions else "N/A"},
            {"Category": "Doors & Portals", "Description": "Interior Passages & Entrances", "Count": num_doors, "Share": "Topological Portals"},
            {"Category": "Exterior Windows", "Description": "Facade Daylight Openings", "Count": num_windows, "Share": "Daylight Openings"},
            {"Category": "Structural Partitions", "Description": "Load-Bearing & Interior Walls", "Count": num_walls, "Share": f"Area: {meta.get('total_wall_area_px', 0):,} px"},
        ]
        inv_df = pd.DataFrame(inventory_data)
        st.dataframe(inv_df, **STRETCH_KW, hide_index=True)

        # Export & Download Center
        st.markdown("### 📥 Export & Download Center")
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            csv_data = inv_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Extraction Report (CSV)",
                data=csv_data,
                file_name=f"floorplan_{active_plan_id}_extraction_report.csv",
                mime="text/csv",
                **STRETCH_KW
            )
        with dcol2:
            import json
            json_meta = {
                "floor_plan_id": active_plan_id,
                "summary": inventory_data,
                "metadata": {k: v for k, v in meta.items() if not k.startswith("_")}
            }
            json_data = json.dumps(json_meta, indent=2).encode("utf-8")
            st.download_button(
                "📥 Download Spatial Metadata (JSON)",
                data=json_data,
                file_name=f"floorplan_{active_plan_id}_metadata.json",
                mime="application/json",
                **STRETCH_KW
            )

        st.markdown("---")
        # Collapsed Technical Details for Evaluators & Administrators
        with st.expander("🛠️ Technical Details & Dataset Disclosures (For Evaluators & Administrators)", expanded=False):
            st.markdown("""
            **Dataset Architecture & Methodological Notes:**
            - **CVC-FP Benchmark Dataset:** Architectural floor plan rasters paired with multi-class semantic segmentation masks.
            - **Scale Absence:** Source drawings omit metric scale calibration bars; all dimensional areas and routes are calculated in pixels ($px$).
            - **Zero-Hallucination Protocol:** Measurements, room counts, and routes are derived strictly from computer-vision segmentation masks and stored relational records.
            """)
            st.json(meta)
    else:
        st.info("No extraction metadata found for this floor plan.")
