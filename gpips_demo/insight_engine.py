from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


DIMENSIONS = {
    "battery": ("battery_assess", "battery_comment", "battery_emotion_assess", "续航 / 电池"),
    "camera": ("cam_assess", "cam_comment", "cam_emotion_assess", "影像 / 相机"),
    "performance": ("performance_assess", "performance_comment", "performance_emotion_assess", "性能 / 游戏"),
    "screen": ("screen_assess", "screen_comment", "screen_emotion_assess", "屏幕"),
    "software": ("software_assess", "software_comment", "software_emotion_assess", "软件体验"),
    "price": ("price_assess", "price_comment", "price_emotion_assess", "价格 / 性价比"),
}


@dataclass(frozen=True)
class DemoInput:
    market: str
    price_min: int
    price_max: int
    target_user: str
    focus: list[str]
    channel: str

    @property
    def price_band(self) -> str:
        return f"{self.price_min // 1000}K-{self.price_max // 1000}K INR"


def filter_ratings(ratings: pd.DataFrame, demo: DemoInput) -> pd.DataFrame:
    if ratings.empty or "int_price" not in ratings:
        return pd.DataFrame()
    return ratings[(ratings["int_price"] >= demo.price_min) & (ratings["int_price"] < demo.price_max)].copy()


def filter_reviews(reviews: pd.DataFrame, demo: DemoInput) -> pd.DataFrame:
    if reviews.empty:
        return pd.DataFrame()
    if "country_alpha2" in reviews:
        india = reviews[reviews["country_alpha2"].eq("IN")]
        return india.copy() if not india.empty else reviews.copy()
    return reviews.copy()


def search_knowledge(knowledge: pd.DataFrame, query: str, top_k: int = 8) -> pd.DataFrame:
    if knowledge.empty:
        return knowledge
    terms = [term.lower() for term in query.replace("/", " ").replace("+", " ").split() if len(term) > 1]
    cn_terms = ["机会", "小屏", "轻薄", "大电池", "续航", "快充", "耐用", "影像", "游戏", "5G", "AI", "印度"]

    def score(text: str) -> int:
        lowered = text.lower()
        return sum(lowered.count(term) for term in terms) + sum(text.count(term) for term in cn_terms)

    ranked = knowledge.copy()
    ranked["score"] = ranked["text"].map(score)
    return ranked[ranked["score"] > 0].sort_values("score", ascending=False).head(top_k)


def brand_distribution(ratings: pd.DataFrame) -> pd.DataFrame:
    if ratings.empty or "brand" not in ratings:
        return pd.DataFrame(columns=["brand", "count"])
    return (
        ratings["brand"]
        .fillna("unknown")
        .value_counts()
        .head(10)
        .rename_axis("brand")
        .reset_index(name="count")
    )


def dimension_scores(ratings: pd.DataFrame) -> pd.DataFrame:
    records = []
    for key, (score_col, _, _, label) in DIMENSIONS.items():
        if score_col in ratings:
            value = ratings[score_col].dropna().mean()
            if pd.notna(value):
                records.append({"dimension": label, "score": round(float(value), 2)})
    return pd.DataFrame(records)


def pain_points(reviews: pd.DataFrame) -> pd.DataFrame:
    records = []
    for key, (_, comment_col, emotion_col, label) in DIMENSIONS.items():
        if comment_col not in reviews or emotion_col not in reviews:
            continue
        scoped = reviews[reviews[comment_col].astype(str).str.len() > 0]
        negative = scoped[scoped[emotion_col].eq("差评")]
        positive = scoped[scoped[emotion_col].eq("好评")]
        total = len(scoped)
        if total:
            records.append(
                {
                    "dimension": label,
                    "negative": len(negative),
                    "positive": len(positive),
                    "negative_rate": round(len(negative) / total, 2),
                }
            )
    return pd.DataFrame(records).sort_values(["negative", "negative_rate"], ascending=False)


def review_examples(reviews: pd.DataFrame, limit: int = 5) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for _, row in reviews.iterrows():
        negative_dims = []
        for _, (_, comment_col, emotion_col, label) in DIMENSIONS.items():
            if row.get(emotion_col) == "差评" and str(row.get(comment_col, "")).strip():
                negative_dims.append(str(row.get(comment_col)))
        if not negative_dims:
            continue
        examples.append(
            {
                "product": str(row.get("name", "")),
                "brand": str(row.get("brand", "")),
                "country": str(row.get("country_alpha2", "")),
                "channel": str(row.get("channel", "")),
                "tags": "；".join(negative_dims[:3]),
                "comment": str(row.get("comment_translation") or row.get("comment") or "")[:260],
            }
        )
        if len(examples) >= limit:
            break
    return examples


def generate_opportunities(demo: DemoInput, data: dict[str, Any]) -> list[dict[str, Any]]:
    ratings = filter_ratings(data["ratings"], demo)
    reviews = filter_reviews(data["reviews"], demo)
    knowledge = data["knowledge"]
    knowledge_hits = search_knowledge(knowledge, " ".join(demo.focus) + " 小屏 轻薄 大电池 耐用 游戏 AI 5G")
    pains = pain_points(reviews)
    brands = brand_distribution(ratings)

    top_brands = brands["brand"].head(5).tolist() if not brands.empty else []
    top_pains = pains["dimension"].head(3).tolist() if not pains.empty else []

    base_evidence = {
        "price_band": demo.price_band,
        "top_brands": top_brands,
        "top_pain_points": top_pains,
        "knowledge_hits": knowledge_hits[["source", "text"]].head(4).to_dict("records")
        if not knowledge_hits.empty
        else [],
    }

    return [
        {
            "id": "OPP-IN-001",
            "title": f"{demo.price_band} 小屏轻薄 + 大电池机会",
            "priority": "High",
            "confidence": 0.86,
            "target_user": demo.target_user,
            "summary": "中端价位存在小屏握持、戴壳轻薄和长续航的组合机会，适合做成差异化产品 brief。",
            "rules": [
                "知识库明确出现 10-20K 档位小屏偏好和 5500-6500mAh 电池需求",
                "评分数据可按价格段定位主流竞品和评价短板",
                "评论数据可追溯到续航、性能、价格、软件等用户反馈",
                "5G 已成为基础配置，差异化应转向体验组合",
            ],
            "recommendation": {
                "positioning": "Compact Power Phone for everyday India",
                "specs": ["5G", "6000mAh battery", "45W charging", "compact straight display", "metal-like durable design", "AI camera enhancement"],
                "marketing": ["戴壳后依然好握", "一整天续航", "AI 影像增强", "T2/T3 城市强信号沟通"],
            },
            "evidence": base_evidence,
        },
        {
            "id": "OPP-IN-002",
            "title": f"{demo.price_band} 耐用防护 + 长续航机会",
            "priority": "High",
            "confidence": 0.81,
            "target_user": "T2/T3 城市通勤与线下渠道用户",
            "summary": "印度雨季、通勤颠簸、普遍戴壳等场景，使防护、耐摔、防污水和电池寿命卖点更容易被理解。",
            "rules": [
                "调研报告明确提到 IP64/IP68/IP69、防摔、防污水",
                "大电池和快充是中低价位强需求",
                "耐用卖点可以降低参数同质化压力",
            ],
            "recommendation": {
                "positioning": "Durable 5G Battery Phone",
                "specs": ["IP64/IP68 story", "6000mAh battery", "45W charger", "reinforced frame", "anti-smudge screen story"],
                "marketing": ["雨季安心", "通勤耐用", "电池寿命可感知"],
            },
            "evidence": base_evidence,
        },
        {
            "id": "OPP-IN-003",
            "title": f"{demo.price_band} 游戏高帧 + 散热体验机会",
            "priority": "Medium",
            "confidence": 0.74,
            "target_user": "BGMI 年轻玩家和夜间游戏用户",
            "summary": "报告显示 BGMI、高帧、晚间游戏和高环温场景突出，可作为年轻用户细分产品方向。",
            "rules": [
                "手游调研显示高帧是强购因",
                "晚间 22:00-24:00 是集中游戏时间",
                "高环温游戏场景对散热和续航提出要求",
            ],
            "recommendation": {
                "positioning": "Affordable Smooth Gaming 5G Phone",
                "specs": ["120Hz display", "gaming mode", "thermal story", "large battery", "stereo speaker"],
                "marketing": ["BGMI 稳帧", "晚间游戏不断电", "通勤游戏强信号"],
            },
            "evidence": base_evidence,
        },
    ]


def api_trace(demo: DemoInput, opportunity_id: str = "OPP-IN-001") -> list[dict[str, Any]]:
    return [
        {
            "method": "GET",
            "path": f"/api/v1/products?market=IN&price_min={demo.price_min}&price_max={demo.price_max}",
            "purpose": "按印度价格段查询产品与评分数据",
        },
        {
            "method": "GET",
            "path": "/api/v1/user?market=IN&dimension=battery,camera,performance",
            "purpose": "查询印度用户评论和情绪痛点",
        },
        {
            "method": "POST",
            "path": "/api/v1/knowledge/search",
            "purpose": "检索印度调研报告、简报和机会点段落",
            "body": {"query": " ".join(demo.focus), "top_k": 8},
        },
        {
            "method": "GET",
            "path": f"/api/v1/opportunity/detail?id={opportunity_id}",
            "purpose": "返回机会点详情、触发规则和证据链",
        },
        {
            "method": "POST",
            "path": "/api/v1/recommendation",
            "purpose": "生成产品定位、配置和营销建议",
        },
    ]

