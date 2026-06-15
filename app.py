from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tempfile

import pandas as pd
import streamlit as st

from gpips_demo.data_loader import DEFAULT_ZIP, load_all
from gpips_demo.insight_engine import (
    DemoInput,
    api_trace,
    brand_distribution,
    dimension_scores,
    filter_ratings,
    filter_reviews,
    generate_opportunities,
    pain_points,
    review_examples,
    search_knowledge,
)


st.set_page_config(
    page_title="GPIPS India Opportunity Demo",
    page_icon="",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def cached_load(zip_path: str) -> dict:
    return load_all(Path(zip_path))


def save_uploaded_zip(uploaded_file) -> str:
    raw = uploaded_file.getvalue()
    digest = hashlib.sha256(raw).hexdigest()[:12]
    target = Path(tempfile.gettempdir()) / f"gpips_source_{digest}.zip"
    if not target.exists():
        target.write_bytes(raw)
    return str(target)


def section_label(step: str, title: str, subtitle: str) -> None:
    st.markdown(f"### {step} {title}")
    st.caption(subtitle)


def render_api_trace(demo: DemoInput, opportunity_id: str = "OPP-IN-001") -> None:
    for item in api_trace(demo, opportunity_id):
        with st.expander(f"{item['method']} {item['path']}"):
            st.write(item["purpose"])
            if "body" in item:
                st.json(item["body"])


def render_opportunity_card(opportunity: dict, expanded: bool = False) -> None:
    with st.expander(
        f"{opportunity['id']} · {opportunity['title']} · {opportunity['priority']} · {int(opportunity['confidence'] * 100)}%",
        expanded=expanded,
    ):
        left, right = st.columns([1.1, 0.9])
        with left:
            st.subheader(opportunity["summary"])
            st.markdown("**触发规则**")
            for rule in opportunity["rules"]:
                st.write(f"- {rule}")
            st.markdown("**推荐定位**")
            st.info(opportunity["recommendation"]["positioning"])
            st.markdown("**建议配置**")
            st.write(" / ".join(opportunity["recommendation"]["specs"]))
            st.markdown("**营销表达**")
            st.write(" / ".join(opportunity["recommendation"]["marketing"]))
        with right:
            evidence = opportunity["evidence"]
            st.metric("Price Band", evidence["price_band"])
            st.write("**Top Brands**")
            st.write(", ".join(evidence["top_brands"]) or "No data")
            st.write("**Top User Pain Points**")
            st.write(", ".join(evidence["top_pain_points"]) or "No data")
            st.write("**Knowledge Evidence**")
            for hit in evidence["knowledge_hits"][:3]:
                st.caption(hit["source"])
                st.write(hit["text"][:220])


st.markdown(
    """
    <style>
    .block-container { padding-top: 1.8rem; }
    div[data-testid="stMetric"] {
        background: #f7f7f8;
        border: 1px solid #ececef;
        border-radius: 8px;
        padding: 12px;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 14px;
        background: #f7f7f8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("GPIPS India Opportunity Intelligence Demo")
st.caption("Data Layer → Knowledge Layer → Insight Engine → Opportunity Pool → Recommendation")

with st.sidebar:
    st.header("Demo Input")
    uploaded_zip = st.file_uploader("Upload source zip", type=["zip"])
    if uploaded_zip is not None:
        zip_path = save_uploaded_zip(uploaded_zip)
        st.success("Using uploaded ZIP")
    else:
        zip_path = st.text_input("Source zip", value=str(DEFAULT_ZIP))
        st.caption("Local default path is for your Mac. On Streamlit Cloud, upload the ZIP above.")
    market = st.selectbox("Market", ["India"], index=0)
    price_band_label = st.selectbox("Price Band", ["10K-15K INR", "15K-20K INR", "20K-30K INR"], index=1)
    price_map = {
        "10K-15K INR": (10000, 15000),
        "15K-20K INR": (15000, 20000),
        "20K-30K INR": (20000, 30000),
    }
    target_user = st.selectbox(
        "Target User",
        ["T2/T3 young replacement buyers", "commuter users", "BGMI young gamers", "offline value buyers"],
    )
    focus = st.multiselect(
        "Focus Areas",
        ["battery", "compact design", "camera", "5G", "durability", "gaming", "AI", "price"],
        default=["battery", "compact design", "camera", "5G", "durability"],
    )
    channel = st.selectbox("Channel", ["Flipkart + YouTube", "Flipkart", "YouTube"], index=0)
    run_demo = st.button("Generate Opportunity", type="primary", width="stretch")

price_min, price_max = price_map[price_band_label]
demo = DemoInput(
    market=market,
    price_min=price_min,
    price_max=price_max,
    target_user=target_user,
    focus=focus,
    channel=channel,
)

try:
    data = cached_load(zip_path)
except Exception as exc:
    st.error(f"数据加载失败：{exc}")
    st.stop()

ratings = filter_ratings(data["ratings"], demo)
reviews = filter_reviews(data["reviews"], demo)
brands = brand_distribution(ratings)
scores = dimension_scores(ratings)
pains = pain_points(reviews)
knowledge_query = " ".join(focus) + " 印度 中端 手机 小屏 轻薄 大电池 耐用 游戏 AI 5G"
knowledge_hits = search_knowledge(data["knowledge"], knowledge_query, top_k=10)
opportunities = generate_opportunities(demo, data)

source_files = data["sources"]
all_ratings = data["ratings"]
all_reviews = data["reviews"]
product_matrix = data["product_matrix"]
knowledge = data["knowledge"]

metric_cols = st.columns(5)
metric_cols[0].metric("Ratings", f"{len(all_ratings):,}")
metric_cols[1].metric("India Reviews", f"{len(reviews):,}")
metric_cols[2].metric("Product Matrix", f"{len(product_matrix):,}")
metric_cols[3].metric("Knowledge Chunks", f"{len(knowledge):,}")
metric_cols[4].metric("Opportunities", f"{len(opportunities)}")

tab_guided, tab_market, tab_knowledge, tab_pool, tab_api = st.tabs(
    ["Guided Demo", "Market Data", "Knowledge Search", "Opportunity Pool", "API Trace"]
)

with tab_guided:
    st.subheader("Automated Insight Flow")
    st.write(
        f"业务问题：在 **{demo.market} {demo.price_band}**，面向 **{demo.target_user}**，"
        f"围绕 **{', '.join(demo.focus)}**，系统如何生成机会点和推荐配置？"
    )

    if not run_demo:
        st.info("点击左侧 Generate Opportunity，演示 Data → Knowledge → Insight → Recommendation 的自动化输出。")

    section_label("Step 1", "Data Layer", "统一读取产品矩阵、Flipkart 评分、YouTube 评论和 IDC 数据。")
    c1, c2, c3 = st.columns(3)
    c1.metric("Selected Products", f"{len(ratings):,}")
    c2.metric("Avg Rating", f"{ratings['total_comment'].dropna().mean():.2f}" if not ratings.empty else "N/A")
    c3.metric("Review Samples", f"{len(reviews):,}")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("**Brand Distribution**")
        if not brands.empty:
            st.bar_chart(brands.set_index("brand"))
        else:
            st.warning("No brand data for this price band.")
    with chart_right:
        st.markdown("**Rating Dimensions**")
        if not scores.empty:
            st.bar_chart(scores.set_index("dimension"))
        else:
            st.warning("No rating dimension data.")

    section_label("Step 2", "Knowledge Layer", "检索印度市场调研、信息简报和机会点段落。")
    chips = ["小屏需求", "大电池", "45W快充", "耐用防护", "AI影像", "游戏高帧", "T2/T3城市"]
    st.write(" ".join([f"`{chip}`" for chip in chips]))
    for _, row in knowledge_hits.head(5).iterrows():
        with st.expander(f"{row['source']} · Paragraph {row['paragraph_id']} · score {row['score']}"):
            st.write(row["text"])

    section_label("Step 3", "Insight Engine", "规则引擎组合价格段、痛点、报告证据，生成机会池。")
    render_opportunity_card(opportunities[0], expanded=True)

    section_label("Step 4", "Recommendation", "输出产品方向、建议配置和可对外演示的产品 brief。")
    rec = opportunities[0]["recommendation"]
    rec_cols = st.columns([0.9, 1.1])
    with rec_cols[0]:
        st.metric("Primary Opportunity", opportunities[0]["title"])
        st.metric("Confidence", f"{int(opportunities[0]['confidence'] * 100)}%")
        st.metric("Priority", opportunities[0]["priority"])
    with rec_cols[1]:
        st.markdown("**Product Brief**")
        st.success(rec["positioning"])
        st.write("**Core Specs:** " + " / ".join(rec["specs"]))
        st.write("**Messaging:** " + " / ".join(rec["marketing"]))

with tab_market:
    st.subheader("Market Data Explorer")
    st.caption("用于证明 Data Layer 能按价格段、品牌、评分和用户评论查询。")

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Price-band Products from Rating Data**")
        display_cols = [
            col
            for col in ["name", "brand", "int_price", "channel", "battery_assess", "performance_assess", "cam_assess", "total_comment", "comment_num"]
            if col in ratings
        ]
        st.dataframe(ratings[display_cols].head(100), width="stretch", hide_index=True)
    with right:
        st.markdown("**User Pain Points from India Reviews**")
        if not pains.empty:
            st.dataframe(pains, width="stretch", hide_index=True)
            st.bar_chart(pains.set_index("dimension")[["negative", "positive"]])
        else:
            st.warning("No review pain point data.")

    st.markdown("**Negative Review Evidence**")
    for example in review_examples(reviews):
        with st.expander(f"{example['product']} · {example['brand']} · {example['country']} · {example['channel']}"):
            st.write(example["tags"])
            st.caption(example["comment"])

    st.markdown("**Product Matrix Sample**")
    st.dataframe(product_matrix.head(80), width="stretch", hide_index=True)

with tab_knowledge:
    st.subheader("Knowledge Search")
    query = st.text_input("Search query", value=knowledge_query)
    top_k = st.slider("Top K", min_value=3, max_value=20, value=8)
    results = search_knowledge(knowledge, query, top_k=top_k)
    st.caption(f"{len(results)} matched paragraphs")
    for _, row in results.iterrows():
        with st.expander(f"{row['source']} · Paragraph {row['paragraph_id']} · score {row['score']}"):
            st.write(row["text"])

with tab_pool:
    st.subheader("Opportunity Pool")
    st.caption("机会点来自规则引擎，不做 AI 预测，强调可解释和可追溯。")
    for idx, opportunity in enumerate(opportunities):
        render_opportunity_card(opportunity, expanded=idx == 0)

with tab_api:
    st.subheader("API Trace / Playground")
    st.caption("前端 Demo 当前直接调用本地函数；这里展示最终 FastAPI 化时的接口路径和请求体。")
    render_api_trace(demo)
    st.markdown("**Recommendation Request**")
    st.json(
        {
            "target_market": "India",
            "price_band": demo.price_band,
            "target_user": demo.target_user,
            "priority": demo.focus,
        }
    )
    st.markdown("**Primary Opportunity JSON**")
    st.json(json.loads(json.dumps(opportunities[0], ensure_ascii=False)))

with st.expander("Source Files"):
    st.write(f"Extracted root: `{source_files.root}`")
    st.write(f"Rating: `{source_files.rating.name}`")
    st.write(f"Reviews: `{source_files.reviews.name}`")
    st.write(f"Product matrix: `{source_files.product_matrix.name}`")
    st.write(f"IDC: `{source_files.idc.name}`")
    st.write("Knowledge docs: " + ", ".join(path.name for path in source_files.docs))
