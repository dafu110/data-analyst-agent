from __future__ import annotations

from data_analyst_agent.models import DatasetProfile, SemanticRole


ROLE_KEYWORDS = {
    "date": ("date", "日期", "时间", "day", "month", "月份", "year", "年份"),
    "region": ("region", "地区", "区域", "省", "城市", "city", "area", "门店"),
    "product": ("product", "产品", "商品", "sku", "品类", "category", "类别"),
    "channel": ("channel", "渠道", "来源", "source", "platform", "平台"),
    "customer": ("customer", "客户", "用户", "会员", "user", "client"),
    "order": ("order", "订单", "orderid", "订单号"),
    "revenue": ("revenue", "sales", "销售额", "收入", "成交额", "gmv", "mrr", "arr", "amount", "金额"),
    "profit": ("profit", "利润", "毛利", "净利", "margin"),
    "cost": ("cost", "成本", "费用", "expense"),
    "units": ("units", "销量", "件数", "数量", "qty", "quantity", "volume"),
    "discount": ("discount", "折扣", "优惠", "coupon", "rebate"),
    "price": ("price", "价格", "单价", "客单价"),
}


def infer_semantic_roles(profile: DatasetProfile, data_dictionary: dict[str, str] | None = None) -> list[SemanticRole]:
    roles: list[SemanticRole] = []
    used_columns: set[str] = set()
    dictionary_roles = build_dictionary_roles(profile, data_dictionary or {})
    for role in dictionary_roles:
        roles.append(role)
        used_columns.add(role.column)
    for role, keywords in ROLE_KEYWORDS.items():
        if any(existing.role == role for existing in roles):
            continue
        match = best_column_match(profile, keywords, used_columns)
        if match:
            column, confidence, reason = match
            roles.append(SemanticRole(role=role, column=column, confidence=confidence, reason=reason))
            used_columns.add(column)
    return roles


def build_dictionary_roles(profile: DatasetProfile, data_dictionary: dict[str, str]) -> list[SemanticRole]:
    roles: list[SemanticRole] = []
    valid_roles = set(ROLE_KEYWORDS)
    columns = set(profile.column_names)
    for column, role in data_dictionary.items():
        normalized_role = normalize(str(role))
        if column not in columns or normalized_role not in valid_roles:
            continue
        roles.append(
            SemanticRole(
                role=normalized_role,
                column=column,
                confidence=1.0,
                reason="由用户数据字典指定",
            )
        )
    return roles


def best_column_match(
    profile: DatasetProfile,
    keywords: tuple[str, ...],
    used_columns: set[str],
) -> tuple[str, float, str] | None:
    candidates: list[tuple[str, float, str]] = []
    for column in profile.column_names:
        if column in used_columns:
            continue
        normalized = normalize(column)
        for keyword in keywords:
            normalized_keyword = normalize(keyword)
            if normalized == normalized_keyword:
                candidates.append((column, 0.98, f"字段名精确匹配 `{keyword}`"))
            elif normalized_keyword in normalized:
                candidates.append((column, 0.86, f"字段名包含 `{keyword}`"))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0]


def semantic_map(roles: list[SemanticRole]) -> dict[str, str]:
    return {role.role: role.column for role in roles}


def normalize(value: str) -> str:
    return value.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
