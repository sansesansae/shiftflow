from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.sql"
SQLITE_PATH = ROOT / "shiftflow_seed.sqlite"
JSON_PATH = ROOT / "shiftflow_seed.json"

RNG = random.Random(20260805)
NOW = "2026-08-05T09:00:00+08:00"

STORES = [
    ("store_heykj_sh_jingan", "喜茶", "喜茶上海静安嘉里店", "上海", "静安区", "奶茶店"),
    ("store_chagee_hz_mixc", "霸王茶姬", "霸王茶姬杭州万象城店", "杭州", "上城区", "奶茶店"),
    ("store_starbucks_sz_mixc", "星巴克", "星巴克深圳万象天地店", "深圳", "南山区", "咖啡店"),
    ("store_mcd_gz_tianhe", "麦当劳", "麦当劳广州天河城店", "广州", "天河区", "快餐店"),
    ("store_kfc_cd_taikoo", "肯德基", "肯德基成都太古里店", "成都", "锦江区", "快餐店"),
    ("store_luckin_bj_guomao", "瑞幸", "瑞幸北京国贸店", "北京", "朝阳区", "咖啡店"),
]

SHIFT_TEMPLATES = [
    ("tpl_open", "早开班", "06:30", "11:00", ["值班经理", "收银", "调饮师"], "normal"),
    ("tpl_lunch_peak", "午高峰班", "11:00", "15:00", ["收银", "后厨", "调饮师", "咖啡师"], "high"),
    ("tpl_prep", "下午备料班", "14:00", "18:00", ["调饮师", "后厨"], "normal"),
    ("tpl_dinner_peak", "晚高峰班", "17:00", "22:30", ["值班经理", "收银", "后厨", "咖啡师"], "high"),
    ("tpl_close", "闭店班", "20:00", "00:30", ["值班经理", "后厨", "咖啡师"], "high"),
]

NAMES = [
    "李晨",
    "王雅婷",
    "张宇",
    "陈思雨",
    "赵子航",
    "刘嘉怡",
    "周明",
    "孙可",
    "林雨桐",
    "郭浩",
    "何欣",
    "唐佳宁",
]

ROLE_SKILLS = {
    "店长": ["排班审核", "闭店复盘", "人员协调"],
    "值班经理": ["闭店", "收银复核", "高峰协调"],
    "咖啡师": ["咖啡制作", "拉花", "设备清洁"],
    "调饮师": ["茶饮制作", "备料", "出杯质检"],
    "收银": ["点单", "会员核销", "外卖对接"],
    "后厨": ["备餐", "炸制", "食品安全"],
    "外送打包": ["打包", "外卖核对", "骑手交接"],
}


def row_id(prefix: str, *parts: object) -> str:
    text = "_".join(str(part).lower().replace(" ", "_").replace(":", "") for part in parts)
    return f"{prefix}_{text}"


def build_stores() -> list[dict]:
    stores = []
    for store_id, brand, name, city, district, business_type in STORES:
        stores.append(
            {
                "id": store_id,
                "brand": brand,
                "name": name,
                "city": city,
                "district": district,
                "address": f"{city}{district}核心商圈 {RNG.randint(1, 188)} 号",
                "business_type": business_type,
                "opening_time": "06:30" if business_type != "快餐店" else "06:00",
                "closing_time": "00:30" if business_type == "快餐店" else "23:30",
                "status": "active",
                "created_at": NOW,
            }
        )
    return stores


def build_shift_templates() -> list[dict]:
    return [
        {
            "id": template_id,
            "name": name,
            "start_time": start,
            "end_time": end,
            "default_roles": json.dumps(roles, ensure_ascii=False),
            "priority": priority,
        }
        for template_id, name, start, end, roles, priority in SHIFT_TEMPLATES
    ]


def build_employees(stores: list[dict]) -> list[dict]:
    employees = []
    roles = list(ROLE_SKILLS)
    index = 0
    for store in stores:
        for _ in range(8):
            role = roles[index % len(roles)]
            name = NAMES[index % len(NAMES)]
            employee_id = row_id("emp", store["id"], index + 1)
            employees.append(
                {
                    "id": employee_id,
                    "store_id": store["id"],
                    "name": name,
                    "role": role,
                    "skills": json.dumps(ROLE_SKILLS[role], ensure_ascii=False),
                    "weekly_hour_limit": 40,
                    "scheduled_hours": RNG.randint(22, 39),
                    "can_close": 1 if role in {"店长", "值班经理", "咖啡师", "后厨"} else 0,
                    "can_float": 1 if index % 3 == 0 else 0,
                    "phone": f"138{RNG.randint(10000000, 99999999)}",
                    "status": "active",
                    "created_at": NOW,
                }
            )
            index += 1
    return employees


def build_shifts(stores: list[dict], templates: list[dict]) -> list[dict]:
    shifts = []
    start_date = date(2026, 8, 5)
    for store in stores:
        for day_offset in range(7):
            shift_date = start_date + timedelta(days=day_offset)
            for template in templates:
                roles = json.loads(template["default_roles"])
                required_role = RNG.choice(roles)
                required_count = 2 if template["priority"] == "high" else 1
                assigned_count = max(0, required_count - RNG.choice([0, 0, 0, 1]))
                status = "open" if assigned_count < required_count else "filled"
                shifts.append(
                    {
                        "id": row_id("shift", store["id"], shift_date.isoformat(), template["id"], required_role),
                        "store_id": store["id"],
                        "template_id": template["id"],
                        "shift_date": shift_date.isoformat(),
                        "start_time": template["start_time"],
                        "end_time": template["end_time"],
                        "required_role": required_role,
                        "required_count": required_count,
                        "assigned_count": assigned_count,
                        "status": status,
                        "note": "高峰优先补齐" if status == "open" else "",
                        "created_at": NOW,
                    }
                )
    return shifts


def build_assignments(shifts: list[dict], employees: list[dict]) -> list[dict]:
    assignments = []
    by_store: dict[str, list[dict]] = {}
    for employee in employees:
        by_store.setdefault(employee["store_id"], []).append(employee)

    for shift in shifts:
        candidates = [
            employee
            for employee in by_store[shift["store_id"]]
            if employee["role"] == shift["required_role"] or employee["can_float"]
        ]
        RNG.shuffle(candidates)
        for employee in candidates[: shift["assigned_count"]]:
            assignments.append(
                {
                    "id": row_id("asg", shift["id"], employee["id"]),
                    "shift_id": shift["id"],
                    "employee_id": employee["id"],
                    "assignment_status": "assigned",
                    "source": "seed",
                    "created_at": NOW,
                }
            )
    return assignments


def build_change_records(stores: list[dict], shifts: list[dict], employees: list[dict]) -> list[dict]:
    open_shifts = [shift for shift in shifts if shift["status"] == "open"]
    records = []
    for index, shift in enumerate(open_shifts[:10]):
        store_employees = [employee for employee in employees if employee["store_id"] == shift["store_id"]]
        target = RNG.choice(store_employees)
        store = next(store for store in stores if store["id"] == shift["store_id"])
        records.append(
            {
                "id": row_id("chg", index + 1, shift["id"]),
                "store_id": shift["store_id"],
                "shift_id": shift["id"],
                "request_type": RNG.choice(["补位", "换班", "请假后补班"]),
                "original_employee_id": None,
                "target_employee_id": target["id"],
                "reason": f"{store['name']} {shift['shift_date']} {shift['required_role']} 人手不足",
                "risk_flags": json.dumps(
                    RNG.sample(["工时接近上限", "连续晚班", "闭店后早开", "岗位技能匹配"], k=2),
                    ensure_ascii=False,
                ),
                "approval_status": RNG.choice(["pending", "approved", "needs_review"]),
                "requested_by": "门店店长",
                "requested_at": datetime.fromisoformat(NOW).isoformat(),
                "resolved_at": None,
            }
        )
    return records


def insert_many(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    conn.executemany(sql, [[row[column] for column in columns] for row in rows])


def main() -> None:
    stores = build_stores()
    templates = build_shift_templates()
    employees = build_employees(stores)
    shifts = build_shifts(stores, templates)
    assignments = build_assignments(shifts, employees)
    change_records = build_change_records(stores, shifts, employees)

    dataset = {
        "stores": stores,
        "employees": employees,
        "shift_templates": templates,
        "shifts": shifts,
        "shift_assignments": assignments,
        "shift_change_records": change_records,
    }

    JSON_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table, rows in dataset.items():
            insert_many(conn, table, rows)
        conn.commit()
    finally:
        conn.close()

    print(f"Generated {JSON_PATH}")
    print(f"Generated {SQLITE_PATH}")
    print(
        "Counts: "
        + ", ".join(f"{table}={len(rows)}" for table, rows in dataset.items())
    )


if __name__ == "__main__":
    main()
