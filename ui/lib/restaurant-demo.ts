import type { Agent, Message } from "@/lib/types";

type RestaurantBrand =
  | "喜茶"
  | "霸王茶姬"
  | "星巴克"
  | "麦当劳"
  | "肯德基"
  | "瑞幸";

type StoreProfile = {
  brand: RestaurantBrand;
  storeName: string;
  district: string;
};

const STORES: StoreProfile[] = [
  { brand: "喜茶", storeName: "喜茶上海静安嘉里店", district: "静安区" },
  { brand: "霸王茶姬", storeName: "霸王茶姬杭州万象城店", district: "上城区" },
  { brand: "星巴克", storeName: "星巴克深圳万象天地店", district: "南山区" },
  { brand: "麦当劳", storeName: "麦当劳广州天河城店", district: "天河区" },
  { brand: "肯德基", storeName: "肯德基成都太古里店", district: "锦江区" },
  { brand: "瑞幸", storeName: "瑞幸北京国贸店", district: "朝阳区" },
];

const SHIFT_WINDOWS = [
  "早开班 06:30-11:00",
  "午高峰班 11:00-15:00",
  "下午备料班 14:00-18:00",
  "晚高峰班 17:00-22:30",
  "闭店班 20:00-00:30",
];

const ROLE_POOL = ["店长", "值班经理", "咖啡师", "调饮师", "收银", "后厨", "外送打包"];
const FALLBACK_NAMES = ["李晨", "王雅婷", "张宇", "陈思雨", "赵子航", "刘嘉怡"];

const SHIFT_GAPS = [
  {
    store: "麦当劳广州天河城店",
    shift: "晚高峰班 17:00-22:30",
    role: "后厨",
    gap: "缺 1 人",
    urgency: "高",
  },
  {
    store: "喜茶上海静安嘉里店",
    shift: "午高峰班 11:00-15:00",
    role: "调饮师",
    gap: "缺 2 人",
    urgency: "中",
  },
  {
    store: "星巴克深圳万象天地店",
    shift: "闭店班 20:00-00:30",
    role: "咖啡师",
    gap: "需确认 1 人",
    urgency: "中",
  },
];

const COVER_RECOMMENDATIONS = [
  "王雅婷｜调饮师｜可接 17:00-22:30｜本周 29h",
  "陈思雨｜值班经理｜可接闭店班｜本周 39h",
  "刘嘉怡｜收银｜可支援午高峰｜本周 30h",
];

const RULE_ALERTS = [
  "陈思雨本周已 39h，再排闭店班需确认工时上限",
  "张宇连续 3 天晚班，建议优先换早班或休息",
  "闭店班后次日早开班间隔不足，不建议连排",
];

function buildEmployees(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const name = FALLBACK_NAMES[index % FALLBACK_NAMES.length];
    const role = ROLE_POOL[index % ROLE_POOL.length];
    const score = 86 + ((index * 7) % 14);
    const weeklyHours = 24 + ((index * 5) % 19);

    return `${name}｜${role}｜技能分 ${score}｜本周 ${weeklyHours}h`;
  });
}

function buildStarterPrompts(stores: StoreProfile[]) {
  return [
    `${stores[0].storeName} 明天午高峰还差谁`,
    `${stores[3].storeName} 晚高峰少 1 个后厨，帮我找人顶上`,
    `${stores[2].storeName} 有人连续 3 天晚班，还能继续排吗`,
    `帮 ${stores[1].storeName} 做一版周末高峰排班`,
  ];
}

function buildOpeningMessages(stores: StoreProfile[]): Message[] {
  return [
    {
      id: "welcome",
      role: "assistant",
      agent: "门店排班助手",
      content:
        "今天先处理哪家店？你可以直接告诉我门店、班次和缺口，比如“晚高峰少 1 个后厨”或“闭店班没人接”。",
      timestamp: new Date("2026-08-05T09:00:00+08:00"),
      status: "info",
    },
    {
      id: "snapshot",
      role: "assistant",
      agent: "门店排班助手",
      content: [
        "今日需要优先看的门店：",
        `1. ${stores[0].storeName}：午高峰调饮岗偏紧`,
        `2. ${stores[2].storeName}：晚高峰咖啡师排班冲突待确认`,
        `3. ${stores[3].storeName}：闭店班有人请假，需要补位`,
      ].join("\n"),
      timestamp: new Date("2026-08-05T09:01:00+08:00"),
      status: "warning",
    },
  ];
}

export function buildRestaurantAgents(): Agent[] {
  return [
    {
      name: "门店排班助手",
      description: "识别门店诉求，并把问题交给查班、调班或规则专员。",
      handoffs: ["排班协调助手", "规则助手", "门店排班总控"],
      tools: ["route_store_request"],
      input_guardrails: [],
    },
    {
      name: "门店排班总控",
      description: "查看门店班次、工时分布和高峰时段缺口。",
      handoffs: ["排班协调助手", "规则助手", "门店排班助手"],
      tools: ["get_store_schedule", "get_open_shift_gaps"],
      input_guardrails: [],
    },
    {
      name: "排班协调助手",
      description: "推荐顶班人选，处理换班、补班和闭店班补位。",
      handoffs: ["规则助手", "门店排班助手"],
      tools: ["recommend_cover_staff", "assign_shift", "remove_shift"],
      input_guardrails: [],
    },
    {
      name: "规则助手",
      description: "解释餐饮门店工时、连续晚班、闭店班和休息规则。",
      handoffs: ["门店排班助手", "排班协调助手"],
      tools: ["faq_lookup_tool"],
      input_guardrails: [],
    },
  ];
}

export function buildRestaurantDemo() {
  const stores = STORES;
  const employees = buildEmployees(6);

  return {
    brandName: "ShiftFlow 门店排班",
    stores,
    employees,
    shiftWindows: SHIFT_WINDOWS,
    starterPrompts: buildStarterPrompts(stores),
    openingMessages: buildOpeningMessages(stores),
    suggestedQuestion: `${stores[4].storeName} 本周末晚高峰少几个人？优先推荐能做闭店的伙伴`,
    context: {
      current_flow: "等待选择门店和班次",
      覆盖区域: stores.map((store) => store.district).join(" / "),
      当前门店: stores[0].storeName,
      覆盖品牌: stores.map((store) => store.brand).join("、"),
      重点班次: "午高峰班 11:00-15:00",
      今日提醒: `${stores[3].storeName} 闭店班缺 1 人`,
      可用伙伴: employees,
      班次模板: SHIFT_WINDOWS,
      班次缺口: SHIFT_GAPS,
      推荐补位: COVER_RECOMMENDATIONS,
      规则提醒: RULE_ALERTS,
    },
  };
}
