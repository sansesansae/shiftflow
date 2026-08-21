"use client";

import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { ArrowRight, CalendarClock, LineChart, ShieldCheck, Sparkles, Upload } from "lucide-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { AgentPanel } from "@/components/agent-panel";
import { ChatKitPanel } from "@/components/chatkit-panel";
import { buildRestaurantAgents, buildRestaurantDemo } from "@/lib/restaurant-demo";
import { assignStoreShift, fetchForecastSummary, fetchStores, fetchStoreForecasts, fetchStoreShifts, fetchStoreStaff, importStoreMetricsCsv } from "@/lib/api";
import { isSupabaseAuthConfigured, supabase } from "@/lib/supabase";
import type { Agent, AgentEvent, ForecastSummary, GuardrailCheck, LaborForecast, Store, StoreShift, StoreStaff } from "@/lib/types";

const RESTAURANT_DEMO = buildRestaurantDemo();
const DEFAULT_AGENTS: Agent[] = buildRestaurantAgents();

function estimateShiftHours(shift?: StoreShift) {
  if (!shift) return 0;
  const [startHour, startMinute] = shift.start_time.split(":").map(Number);
  const [endHour, endMinute] = shift.end_time.split(":").map(Number);
  const start = startHour + startMinute / 60;
  let end = endHour + endMinute / 60;
  if (end <= start) end += 24;
  return Math.max(end - start, 1);
}

function buildLocalRiskHints(shift?: StoreShift, person?: StoreStaff) {
  if (!shift || !person) return [];
  const hints: string[] = [];
  const skills = person.skills ?? [];
  if (!person.role.includes(shift.required_role) && !skills.includes(shift.required_role)) {
    hints.push(`岗位需确认：班次需要 ${shift.required_role}，当前伙伴是 ${person.role}`);
  }
  const projectedHours = person.scheduled_hours + estimateShiftHours(shift);
  if (projectedHours > person.weekly_hour_limit) {
    hints.push(`工时需确认：补位后预计 ${projectedHours.toFixed(0)}h，超过 ${person.weekly_hour_limit}h`);
  }
  const isClosingShift = shift.template_name.includes("闭店") || Number(shift.end_time.slice(0, 2)) >= 22;
  if (isClosingShift && !person.can_close) {
    hints.push("闭店需确认：该伙伴未标记为可闭店");
  }
  return hints;
}

function formatDeviation(value?: number | null) {
  if (value === null || value === undefined) return "待评估";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function buildDashboardContext(
  stores: Store[],
  shifts: StoreShift[],
  staff: StoreStaff[],
  fallback: Record<string, any>
) {
  const activeStore = stores[0];
  if (!activeStore) return fallback;

  const openShifts = shifts.filter((shift) => shift.open_count > 0);
  const firstOpenShift = openShifts[0] ?? shifts[0];
  const shiftTemplates = Array.from(
    new Set(shifts.slice(0, 8).map((shift) => `${shift.template_name} ${shift.start_time}-${shift.end_time}`))
  );
  const availableStaff = staff
    .slice(0, 6)
    .map((person) => `${person.name}｜${person.role}｜本周 ${person.scheduled_hours}h｜${person.can_close ? "可闭店" : "常规班"}`);

  return {
    ...fallback,
    current_flow: "已连接后端排班数据",
    覆盖区域: stores.map((store) => store.district).join(" / "),
    当前门店: activeStore.name,
    覆盖品牌: stores.map((store) => store.brand).join("、"),
    重点班次: firstOpenShift
      ? `${firstOpenShift.template_name} ${firstOpenShift.start_time}-${firstOpenShift.end_time}`
      : fallback["重点班次"],
    今日提醒: firstOpenShift
      ? `${activeStore.name} ${firstOpenShift.template_name} ${firstOpenShift.required_role} 缺 ${firstOpenShift.open_count} 人`
      : "暂无紧急缺口",
    可用伙伴: availableStaff,
    班次模板: shiftTemplates.length > 0 ? shiftTemplates : fallback["班次模板"],
    班次缺口: openShifts.slice(0, 6).map((shift) => ({
      store: activeStore.name,
      shift: `${shift.template_name} ${shift.start_time}-${shift.end_time}`,
      role: shift.required_role,
      gap: `缺 ${shift.open_count} 人`,
      urgency: shift.open_count >= 2 ? "高" : "中",
    })),
    推荐补位: staff
      .filter((person) => person.can_float || person.can_close)
      .slice(0, 4)
      .map((person) => `${person.name}｜${person.role}｜本周 ${person.scheduled_hours}h｜${person.skills.slice(0, 2).join("、")}`),
    规则提醒: [
      ...staff
        .filter((person) => person.scheduled_hours >= 36)
        .slice(0, 2)
        .map((person) => `${person.name} 本周已 ${person.scheduled_hours}h，再排班前建议确认工时上限`),
      "闭店班后次日早开班间隔不足时，不建议连排",
    ],
  };
}

export default function Home() {
  const [agents] = useState<Agent[]>(DEFAULT_AGENTS);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string>("门店排班助手");
  const [guardrails, setGuardrails] = useState<GuardrailCheck[]>([]);
  const [context, setContext] = useState<Record<string, any>>(RESTAURANT_DEMO.context);
  const [stores, setStores] = useState<Store[]>([]);
  const [shifts, setShifts] = useState<StoreShift[]>([]);
  const [staff, setStaff] = useState<StoreStaff[]>([]);
  const [forecastSummary, setForecastSummary] = useState<ForecastSummary | null>(null);
  const [forecasts, setForecasts] = useState<LaborForecast[]>([]);
  const [selectedShiftId, setSelectedShiftId] = useState("");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [writeToken, setWriteToken] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [authUser, setAuthUser] = useState<User | null>(null);
  const [authSession, setAuthSession] = useState<Session | null>(null);
  const [authMessage, setAuthMessage] = useState(
    isSupabaseAuthConfigured ? "登录后写操作会带上你的身份。" : "前端还未配置 Supabase 登录。"
  );
  const [assignmentMessage, setAssignmentMessage] = useState("输入写入口令后，可以把一个伙伴补到缺口班次里。");
  const [metricsCsvText, setMetricsCsvText] = useState("");
  const [metricsImportMessage, setMetricsImportMessage] = useState("上传 CSV 后，可以把真实小时经营数据写入预测看板。");
  const [isConfirmingAssignment, setIsConfirmingAssignment] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isImportingMetrics, setIsImportingMetrics] = useState(false);
  const [isSigningIn, setIsSigningIn] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function loadDashboardData() {
      try {
        const nextStores = await fetchStores();
        const activeStore = nextStores[0];
        if (!activeStore) return;
        const [nextShifts, nextStaff] = await Promise.all([
          fetchStoreShifts(activeStore.id, { status: "open" }),
          fetchStoreStaff(activeStore.id),
        ]);
        const [nextForecastSummary, nextForecasts] = await Promise.all([
          fetchForecastSummary(activeStore.id),
          fetchStoreForecasts(activeStore.id),
        ]);
        if (!ignore) {
          setStores(nextStores);
          setShifts(nextShifts);
          setStaff(nextStaff);
          setForecastSummary(nextForecastSummary);
          setForecasts(nextForecasts);
          setSelectedShiftId((current) => current || nextShifts.find((shift) => shift.open_count > 0)?.id || "");
          setSelectedEmployeeId((current) => current || nextStaff[0]?.id || "");
          setContext(buildDashboardContext(nextStores, nextShifts, nextStaff, RESTAURANT_DEMO.context));
        }
      } catch (error) {
        console.warn("Failed to load dashboard data, using local fallback.", error);
      }
    }

    void loadDashboardData();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!supabase) return;

    let ignore = false;
    supabase.auth.getSession().then(({ data }) => {
      if (ignore) return;
      setAuthSession(data.session);
      setAuthUser(data.session?.user ?? null);
      if (data.session?.user?.email) {
        setAuthMessage(`已登录：${data.session.user.email}`);
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthSession(session);
      setAuthUser(session?.user ?? null);
      setAuthMessage(session?.user?.email ? `已登录：${session.user.email}` : "已退出登录。");
    });

    return () => {
      ignore = true;
      listener.subscription.unsubscribe();
    };
  }, []);

  async function handleSignIn() {
    if (!supabase) {
      setAuthMessage("请先配置 NEXT_PUBLIC_SUPABASE_URL 和 NEXT_PUBLIC_SUPABASE_ANON_KEY。");
      return;
    }
    if (!loginEmail.trim() || !loginPassword) {
      setAuthMessage("请输入邮箱和密码。");
      return;
    }

    setIsSigningIn(true);
    setAuthMessage("正在登录...");
    const { data, error } = await supabase.auth.signInWithPassword({
      email: loginEmail.trim(),
      password: loginPassword,
    });
    if (error) {
      setAuthMessage(error.message);
    } else {
      setAuthSession(data.session);
      setAuthUser(data.user);
      setLoginPassword("");
      setAuthMessage(`已登录：${data.user.email}`);
    }
    setIsSigningIn(false);
  }

  async function handleSignUp() {
    if (!supabase) {
      setAuthMessage("请先配置 NEXT_PUBLIC_SUPABASE_URL 和 NEXT_PUBLIC_SUPABASE_ANON_KEY。");
      return;
    }
    if (!loginEmail.trim() || !loginPassword) {
      setAuthMessage("请输入邮箱和密码。");
      return;
    }

    setIsSigningIn(true);
    setAuthMessage("正在创建测试账号...");
    const { data, error } = await supabase.auth.signUp({
      email: loginEmail.trim(),
      password: loginPassword,
      options: {
        emailRedirectTo: window.location.origin,
      },
    });
    if (error) {
      setAuthMessage(error.message);
    } else if (data.session) {
      setAuthSession(data.session);
      setAuthUser(data.user);
      setLoginPassword("");
      setAuthMessage(`账号已创建并登录：${data.user?.email}`);
    } else {
      setAuthMessage("账号已创建，请查收邮件完成确认后再登录。");
    }
    setIsSigningIn(false);
  }

  async function handleSignOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setAuthSession(null);
    setAuthUser(null);
    setAuthMessage("已退出登录。");
  }

  async function refreshDashboardData() {
    const activeStore = stores[0] ?? (await fetchStores())[0];
    if (!activeStore) return;
    const [nextStores, nextShifts, nextStaff] = await Promise.all([
      stores.length > 0 ? Promise.resolve(stores) : fetchStores(),
      fetchStoreShifts(activeStore.id, { status: "open" }),
      fetchStoreStaff(activeStore.id),
    ]);
    const [nextForecastSummary, nextForecasts] = await Promise.all([
      fetchForecastSummary(activeStore.id),
      fetchStoreForecasts(activeStore.id),
    ]);
    setStores(nextStores);
    setShifts(nextShifts);
    setStaff(nextStaff);
    setForecastSummary(nextForecastSummary);
    setForecasts(nextForecasts);
    setSelectedShiftId(nextShifts.find((shift) => shift.open_count > 0)?.id || "");
    setSelectedEmployeeId(nextStaff[0]?.id || "");
    setContext(buildDashboardContext(nextStores, nextShifts, nextStaff, RESTAURANT_DEMO.context));
  }

  async function handleAssignShift() {
    const activeStore = stores[0];
    if (!activeStore || !selectedShiftId || !selectedEmployeeId) {
      setAssignmentMessage("请先选择门店缺口班次和补位伙伴。");
      return;
    }
    if (!writeToken.trim()) {
      setAssignmentMessage("请输入写入口令，才可以确认补位。");
      return;
    }
    if (!isConfirmingAssignment) {
      setIsConfirmingAssignment(true);
      setAssignmentMessage("请先核对确认卡，确认班次、伙伴和风险提示无误后再提交。");
      return;
    }

    setIsAssigning(true);
    setAssignmentMessage("正在确认补位...");
    try {
      await assignStoreShift({
        storeId: activeStore.id,
        shiftId: selectedShiftId,
        employeeId: selectedEmployeeId,
        writeToken: writeToken.trim(),
        accessToken: authSession?.access_token,
      });
      await refreshDashboardData();
      setAssignmentMessage("补位成功，班次和伙伴工时已刷新。");
      setIsConfirmingAssignment(false);
    } catch (error) {
      setAssignmentMessage(error instanceof Error ? error.message : "补位失败，请稍后再试。");
    } finally {
      setIsAssigning(false);
    }
  }

  async function handleMetricsFileChange(file?: File) {
    if (!file) return;
    const text = await file.text();
    setMetricsCsvText(text);
    setMetricsImportMessage(`已读取 ${file.name}，点击导入后会刷新预测结果。`);
  }

  async function handleImportMetrics() {
    const activeStore = stores[0];
    if (!activeStore) {
      setMetricsImportMessage("请先等待门店数据加载完成。");
      return;
    }
    if (!writeToken.trim()) {
      setMetricsImportMessage("请输入写入口令，才可以导入经营数据。");
      return;
    }
    if (!metricsCsvText.trim()) {
      setMetricsImportMessage("请先选择一个 CSV 文件。");
      return;
    }

    setIsImportingMetrics(true);
    setMetricsImportMessage("正在导入并刷新预测...");
    try {
      const result = await importStoreMetricsCsv({
        storeId: activeStore.id,
        csvText: metricsCsvText,
        writeToken: writeToken.trim(),
        accessToken: authSession?.access_token,
      });
      await refreshDashboardData();
      setMetricsImportMessage(
        `导入完成：${result.imported_count} 行数据，刷新 ${result.forecast_count} 条预测，发现 ${result.badcase_count} 个复盘点。`
      );
    } catch (error) {
      setMetricsImportMessage(error instanceof Error ? error.message : "导入失败，请检查 CSV 格式。");
    } finally {
      setIsImportingMetrics(false);
    }
  }

  const selectedShift = shifts.find((shift) => shift.id === selectedShiftId);
  const selectedEmployee = staff.find((person) => person.id === selectedEmployeeId);
  const localRiskHints = buildLocalRiskHints(selectedShift, selectedEmployee);
  const previewForecasts = forecasts.slice(0, 5);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(235,94,40,0.16),_transparent_26%),radial-gradient(circle_at_top_right,_rgba(13,110,253,0.14),_transparent_24%),linear-gradient(180deg,_#f9f4ec_0%,_#f3efe7_42%,_#efe9df_100%)] text-stone-900">
      <section className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-6 rounded-[28px] border border-white/70 bg-white/75 px-5 py-4 shadow-[0_18px_60px_rgba(37,33,24,0.08)] backdrop-blur sm:px-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-stone-600">
                <CalendarClock className="h-3.5 w-3.5" />
                {RESTAURANT_DEMO.brandName}
              </div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-stone-950 sm:text-5xl">
                高峰缺人、临时请假、闭店补位，一句话先排起来。
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-stone-600 sm:text-base">
                ShiftFlow 面向奶茶、咖啡和快餐门店，帮店长快速看清今天缺口，找到合适的人，顺手检查工时和排班规则。
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:w-[420px] lg:grid-cols-1">
              <div className="rounded-2xl border border-stone-200/80 bg-stone-50/90 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-stone-500">
                  今日重点
                </div>
                <div className="mt-2 text-lg font-semibold text-stone-900">
                  晚高峰和闭店班
                </div>
                <div className="mt-1 text-sm text-stone-600">
                  先处理最容易影响出餐和关店的班次。
                </div>
              </div>
              <div className="rounded-2xl border border-stone-200/80 bg-stone-50/90 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-stone-500">
                  处理方式
                </div>
                <div className="mt-2 text-lg font-semibold text-stone-900">
                  说门店情况就行
                </div>
                <div className="mt-1 text-sm text-stone-600">
                  不用翻表格，直接问谁能顶、谁会超时。
                </div>
              </div>
            </div>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <Box className="rounded-[32px] border border-stone-200/70 bg-[linear-gradient(135deg,_rgba(255,255,255,0.84),_rgba(255,248,240,0.92))] p-6 shadow-[0_24px_80px_rgba(70,53,35,0.10)] sm:p-8">
            <Chip
              icon={<Sparkles className="h-3.5 w-3.5" />}
              label="今日排班处理中"
              className="w-fit bg-[#eb5e28]/10 text-[#b64b20]"
            />
            <Typography className="mt-5 max-w-2xl text-2xl font-semibold leading-tight text-stone-950 sm:text-4xl">
              从“谁没排上”到“谁能顶班”，把店长最急的排班问题先处理掉。
            </Typography>
            <Typography className="mt-4 max-w-xl text-sm leading-7 text-stone-600 sm:text-base">
              适合多门店巡检、单店临时补人、周末高峰预排。你描述门店、班次和缺口，系统给出可执行的排班建议。
            </Typography>

            <Stack className="mt-8 grid gap-3 sm:grid-cols-2">
              <Button
                variant="contained"
                color="primary"
                endIcon={<ArrowRight className="h-4 w-4" />}
                className="items-start justify-between rounded-3xl bg-stone-950 px-5 py-4 text-left text-white shadow-[0_16px_36px_rgba(20,17,12,0.18)] hover:bg-stone-900"
              >
                  <span className="flex flex-col items-start">
                    <span className="text-sm font-medium">立即体验对话</span>
                    <span className="mt-2 text-sm text-stone-300">
                      试着发起一次缺人、调班或闭店补位请求。
                    </span>
                  </span>
              </Button>

              <Box className="rounded-2xl border border-stone-200 bg-white/80 px-5 py-4">
                <Typography className="text-sm font-medium text-stone-900">
                  可以这样问
                </Typography>
                <Typography className="mt-2 text-sm leading-6 text-stone-600">
                  “{RESTAURANT_DEMO.suggestedQuestion}”
                </Typography>
              </Box>
            </Stack>
          </Box>

          <div className="grid gap-4">
            <div className="rounded-[28px] border border-stone-200/70 bg-white/85 p-6 shadow-[0_24px_60px_rgba(70,53,35,0.08)] backdrop-blur">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-[#0d6efd]/10 p-3 text-[#0d6efd]">
                  <CalendarClock className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-stone-950">先盯住高峰缺口</h3>
                  <p className="text-sm text-stone-600">午高峰、晚高峰、闭店班优先处理</p>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-stone-200/70 bg-white/85 p-6 shadow-[0_24px_60px_rgba(70,53,35,0.08)] backdrop-blur">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-[#eb5e28]/10 p-3 text-[#eb5e28]">
                  <ShieldCheck className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-stone-950">顺手检查排班风险</h3>
                  <p className="text-sm text-stone-600">连续晚班、工时过高、岗位不匹配及时提醒</p>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-stone-200/70 bg-white/85 p-6 shadow-[0_24px_60px_rgba(70,53,35,0.08)] backdrop-blur">
              <div className="text-xs uppercase tracking-[0.22em] text-stone-500">
                门店现场常见问题
              </div>
              <div className="mt-3 text-lg font-semibold text-stone-950">
                员工临时请假、周末客流上涨、闭店班没人接，先把今天能落地的安排做出来。
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-4 lg:grid-cols-3">
            <div className="rounded-[28px] border border-stone-200/70 bg-white/80 p-6 shadow-[0_20px_50px_rgba(60,49,31,0.07)]">
              <div className="text-sm font-semibold text-stone-950">场景 01</div>
            <h3 className="mt-2 text-xl font-semibold text-stone-900">临时缺人，快速找人顶上</h3>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              员工请假、迟到、临时调休时，优先从技能匹配、可用时间和本周工时里找合适人选。
            </p>
          </div>
          <div className="rounded-[28px] border border-stone-200/70 bg-white/80 p-6 shadow-[0_20px_50px_rgba(60,49,31,0.07)]">
            <div className="text-sm font-semibold text-stone-950">场景 02</div>
            <h3 className="mt-2 text-xl font-semibold text-stone-900">高峰排班，一眼看清缺口</h3>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              把门店、班次、岗位和可用伙伴放在同一个视图里，减少来回翻表和反复确认。
            </p>
          </div>
          <div className="rounded-[28px] border border-stone-200/70 bg-white/80 p-6 shadow-[0_20px_50px_rgba(60,49,31,0.07)]">
            <div className="text-sm font-semibold text-stone-950">场景 03</div>
            <h3 className="mt-2 text-xl font-semibold text-stone-900">规则不确定，先问清再排</h3>
            <p className="mt-3 text-sm leading-7 text-stone-600">
              连续晚班、闭店班、休息间隔和本周工时，都可以在安排前先过一遍。
            </p>
          </div>
        </section>

        <section className="mt-8 rounded-[30px] border border-stone-200/70 bg-[linear-gradient(135deg,_rgba(16,185,129,0.10),_rgba(255,255,255,0.88)_42%,_rgba(255,247,237,0.86))] p-6 shadow-[0_22px_60px_rgba(70,53,35,0.08)] backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-800">
                <LineChart className="h-3.5 w-3.5" />
                V2 静默试跑
              </div>
              <h2 className="mt-3 text-2xl font-semibold text-stone-950">先预测人力，再看哪里不准</h2>
              <p className="mt-2 text-sm leading-6 text-stone-600">
                这版不会自动改班表，只在后台用历史小时数据试算未来工时，并和实际到岗做偏差对比。偏差大的时段会进入复盘清单。
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:min-w-[520px]">
              <div className="rounded-3xl border border-white/80 bg-white/80 p-4">
                <div className="text-xs text-stone-500">预测工时</div>
                <div className="mt-2 text-2xl font-semibold text-stone-950">
                  {forecastSummary ? forecastSummary.total_predicted_labor_hours.toFixed(1) : "--"}h
                </div>
              </div>
              <div className="rounded-3xl border border-white/80 bg-white/80 p-4">
                <div className="text-xs text-stone-500">实际工时</div>
                <div className="mt-2 text-2xl font-semibold text-stone-950">
                  {forecastSummary ? forecastSummary.total_actual_labor_hours.toFixed(1) : "--"}h
                </div>
              </div>
              <div className="rounded-3xl border border-white/80 bg-white/80 p-4">
                <div className="text-xs text-stone-500">平均偏差</div>
                <div className="mt-2 text-2xl font-semibold text-stone-950">
                  {forecastSummary ? formatDeviation(forecastSummary.average_abs_deviation_rate) : "--"}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="overflow-hidden rounded-3xl border border-stone-200 bg-white/85">
              <div className="border-b border-stone-100 bg-white/70 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-semibold text-stone-950">导入小时经营数据</div>
                    <div className="mt-1 text-xs leading-5 text-stone-500">
                      CSV 必填列：metric_date, hour, role, order_count, sales_amount, actual_labor_hours
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-stone-200 bg-white px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50">
                      <Upload className="h-4 w-4" />
                      选择 CSV
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        className="hidden"
                        onChange={(event) => void handleMetricsFileChange(event.target.files?.[0])}
                      />
                    </label>
                    <Button
                      variant="contained"
                      disabled={isImportingMetrics}
                      onClick={handleImportMetrics}
                      className="rounded-2xl bg-emerald-700 px-5 text-white hover:bg-emerald-800"
                    >
                      {isImportingMetrics ? "导入中" : "导入并刷新"}
                    </Button>
                  </div>
                </div>
                <div className="mt-3 rounded-2xl bg-stone-50 px-4 py-3 text-xs leading-5 text-stone-600">
                  {metricsImportMessage}
                </div>
              </div>
              <div className="grid grid-cols-[0.75fr_0.7fr_0.7fr_0.7fr_0.7fr] gap-2 border-b border-stone-100 px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">
                <span>时段</span>
                <span>岗位</span>
                <span>预测</span>
                <span>实际</span>
                <span>偏差</span>
              </div>
              {previewForecasts.length > 0 ? (
                previewForecasts.map((item) => (
                  <div
                    key={item.id}
                    className="grid grid-cols-[0.75fr_0.7fr_0.7fr_0.7fr_0.7fr] gap-2 border-b border-stone-100 px-4 py-3 text-sm text-stone-700 last:border-0"
                  >
                    <span>{item.forecast_date} {String(item.hour).padStart(2, "0")}:00</span>
                    <span>{item.role}</span>
                    <span>{item.predicted_labor_hours.toFixed(1)}h</span>
                    <span>{item.actual_labor_hours?.toFixed(1) ?? "待回填"}h</span>
                    <span className={item.status === "badcase" ? "font-semibold text-rose-700" : "text-emerald-700"}>
                      {formatDeviation(item.deviation_rate)}
                    </span>
                  </div>
                ))
              ) : (
                <div className="px-4 py-6 text-sm text-stone-500">预测数据加载中，或当前门店还没有可评估时段。</div>
              )}
            </div>

            <div className="rounded-3xl border border-stone-200 bg-stone-950 p-5 text-white">
              <div className="text-xs uppercase tracking-[0.2em] text-stone-400">复盘重点</div>
              <div className="mt-2 text-2xl font-semibold">
                {forecastSummary?.badcase_count ?? 0} 个高偏差时段
              </div>
              <div className="mt-4 space-y-3">
                {(forecastSummary?.next_focus ?? []).slice(0, 3).map((item) => (
                  <div key={item.id} className="rounded-2xl bg-white/10 p-3 text-sm">
                    <div className="font-medium">
                      {item.store_name}｜{String(item.hour).padStart(2, "0")}:00｜{item.role}
                    </div>
                    <div className="mt-1 text-stone-300">
                      预测 {item.predicted_labor_hours.toFixed(1)}h，实际 {item.actual_labor_hours?.toFixed(1) ?? "--"}h，偏差 {formatDeviation(item.deviation_rate)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-[30px] border border-stone-200/70 bg-white/85 p-6 shadow-[0_22px_60px_rgba(70,53,35,0.08)] backdrop-blur">
          <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr] lg:items-end">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-stone-500">
                店长操作台
              </div>
              <h2 className="mt-2 text-2xl font-semibold text-stone-950">确认补位</h2>
              <p className="mt-2 text-sm leading-6 text-stone-600">
                选择一个还有缺口的班次，再选择伙伴。写入口令只用于本次操作，不会展示在页面文案里。
              </p>
              <p className="mt-3 rounded-2xl bg-stone-50 px-4 py-3 text-sm text-stone-700">
                {assignmentMessage}
              </p>
            </div>

            <div className="grid gap-3">
              <div className="grid gap-3 rounded-3xl border border-stone-200 bg-stone-50/70 p-4 md:grid-cols-[1fr_1fr_auto] md:items-center">
                <TextField
                  label="登录邮箱"
                  value={loginEmail}
                  onChange={(event) => setLoginEmail(event.target.value)}
                  size="small"
                  disabled={Boolean(authUser)}
                />
                <TextField
                  label="登录密码"
                  type="password"
                  value={loginPassword}
                  onChange={(event) => setLoginPassword(event.target.value)}
                  size="small"
                  disabled={Boolean(authUser)}
                />
                <div className="flex gap-2">
                  {authUser ? (
                    <Button variant="outlined" onClick={handleSignOut} className="rounded-2xl">
                      退出
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="contained"
                        disabled={isSigningIn || !isSupabaseAuthConfigured}
                        onClick={handleSignIn}
                        className="rounded-2xl bg-stone-950 text-white hover:bg-stone-900"
                      >
                        {isSigningIn ? "处理中" : "登录"}
                      </Button>
                      <Button
                        variant="outlined"
                        disabled={isSigningIn || !isSupabaseAuthConfigured}
                        onClick={handleSignUp}
                        className="rounded-2xl"
                      >
                        创建测试账号
                      </Button>
                    </>
                  )}
                </div>
                <p className="md:col-span-3 text-sm text-stone-600">{authMessage}</p>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
              <TextField
                select
                label="缺口班次"
                value={selectedShiftId}
                onChange={(event) => {
                  setSelectedShiftId(event.target.value);
                  setIsConfirmingAssignment(false);
                }}
                size="small"
              >
                {shifts.filter((shift) => shift.open_count > 0).map((shift) => (
                  <MenuItem key={shift.id} value={shift.id}>
                    {shift.template_name} {shift.start_time}-{shift.end_time} 缺 {shift.open_count}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                label="补位伙伴"
                value={selectedEmployeeId}
                onChange={(event) => {
                  setSelectedEmployeeId(event.target.value);
                  setIsConfirmingAssignment(false);
                }}
                size="small"
              >
                {staff.map((person) => (
                  <MenuItem key={person.id} value={person.id}>
                    {person.name}｜{person.role}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                label="写入口令"
                type="password"
                value={writeToken}
                onChange={(event) => {
                  setWriteToken(event.target.value);
                  setIsConfirmingAssignment(false);
                }}
                size="small"
              />
              <Button
                variant="contained"
                disabled={isAssigning}
                onClick={handleAssignShift}
                className="rounded-2xl bg-[#eb5e28] px-5 text-white hover:bg-[#d04f1f]"
              >
                {isAssigning ? "处理中" : isConfirmingAssignment ? "确认提交" : "生成确认卡"}
              </Button>
              </div>
              {isConfirmingAssignment && selectedShift && selectedEmployee ? (
                <div className="rounded-3xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-950">
                  <div className="font-semibold text-stone-950">补位确认卡</div>
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    <div className="rounded-2xl bg-white/70 p-3">
                      <div className="text-xs text-stone-500">班次</div>
                      <div className="mt-1 font-medium">
                        {selectedShift.template_name} {selectedShift.start_time}-{selectedShift.end_time}
                      </div>
                      <div className="mt-1 text-xs text-stone-600">
                        {selectedShift.shift_date}｜{selectedShift.required_role}｜缺 {selectedShift.open_count} 人
                      </div>
                    </div>
                    <div className="rounded-2xl bg-white/70 p-3">
                      <div className="text-xs text-stone-500">伙伴</div>
                      <div className="mt-1 font-medium">{selectedEmployee.name}</div>
                      <div className="mt-1 text-xs text-stone-600">
                        {selectedEmployee.role}｜本周 {selectedEmployee.scheduled_hours}h →{" "}
                        {(selectedEmployee.scheduled_hours + estimateShiftHours(selectedShift)).toFixed(0)}h
                      </div>
                    </div>
                    <div className="rounded-2xl bg-white/70 p-3">
                      <div className="text-xs text-stone-500">本地预检</div>
                      <div className="mt-1 font-medium">
                        {localRiskHints.length > 0 ? "有需确认项" : "未发现明显风险"}
                      </div>
                      <div className="mt-1 text-xs text-stone-600">
                        后端提交时还会做最终权限和规则校验。
                      </div>
                    </div>
                  </div>
                  {localRiskHints.length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {localRiskHints.map((hint) => (
                        <div key={hint} className="rounded-2xl border border-amber-200 bg-white/70 px-3 py-2 text-xs">
                          {hint}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </section>

        <section className="mt-8 grid flex-1 gap-4 lg:min-h-[820px] lg:grid-cols-[0.9fr_1.1fr]">
          <AgentPanel
            agents={agents}
            currentAgent={currentAgent}
            events={events}
            guardrails={guardrails}
            context={context}
          />
          <ChatKitPanel
            onAgentChange={(agentName, nextContext) => {
              setCurrentAgent(agentName);
              setContext(
                nextContext && Object.keys(nextContext).length > 0
                  ? nextContext
                  : { ...RESTAURANT_DEMO.context, current_flow: `正在处理：${agentName}` }
              );
              setEvents([]);
              setGuardrails([]);
            }}
            onResponseEnd={() => undefined}
          />
        </section>
      </section>
    </main>
  );
}
