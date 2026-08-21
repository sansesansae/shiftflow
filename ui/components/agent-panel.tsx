"use client";

import { AlertTriangle, CalendarDays, CheckCircle2, Clock, Store, Users } from "lucide-react";
import type { Agent, AgentEvent, GuardrailCheck } from "@/lib/types";

interface AgentPanelProps {
  agents: Agent[];
  currentAgent: string;
  events: AgentEvent[];
  guardrails: GuardrailCheck[];
  context: Record<string, any>;
}

export function AgentPanel({
  agents: _agents,
  currentAgent: _currentAgent,
  events: _events,
  guardrails: _guardrails,
  context,
}: AgentPanelProps) {
  const availableStaff = Array.isArray(context["可用伙伴"]) ? context["可用伙伴"] : [];
  const shiftTemplates = Array.isArray(context["班次模板"]) ? context["班次模板"] : [];
  const shiftGaps = Array.isArray(context["班次缺口"]) ? context["班次缺口"] : [];
  const recommendations = Array.isArray(context["推荐补位"]) ? context["推荐补位"] : [];
  const ruleAlerts = Array.isArray(context["规则提醒"]) ? context["规则提醒"] : [];
  const currentStore = context["当前门店"] ?? "喜茶上海静安嘉里店";
  const staffingAlert = context["今日提醒"] ?? "暂无紧急缺口";
  const focusShift = context["重点班次"] ?? "午高峰班 11:00-15:00";
  const brands = context["覆盖品牌"] ?? "喜茶、霸王茶姬、星巴克、麦当劳、肯德基、瑞幸";

  return (
    <div className="flex h-full min-h-[720px] flex-col rounded-[30px] border border-stone-200/80 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(247,244,239,0.92))] shadow-[0_24px_60px_rgba(70,53,35,0.08)]">
      <div className="flex h-16 items-center gap-3 rounded-t-[30px] border-b border-stone-200/70 bg-stone-950 px-5 text-white">
        <Store className="h-5 w-5" />
        <h1 className="text-sm font-semibold sm:text-base lg:text-lg">
          今日排班看板
        </h1>
        <span className="ml-auto text-xs font-light tracking-[0.18em] opacity-70">
          ShiftFlow
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-blue-50 p-2 text-blue-600">
              <Store className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs text-stone-500">正在关注</div>
              <div className="mt-1 text-base font-semibold text-stone-950">{currentStore}</div>
              <div className="mt-1 text-xs leading-5 text-stone-500">{brands}</div>
            </div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-900">
              <AlertTriangle className="h-4 w-4" />
              需要补位
            </div>
            <p className="mt-3 text-sm leading-6 text-amber-950">{staffingAlert}</p>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-blue-900">
              <Clock className="h-4 w-4" />
              先看班次
            </div>
            <p className="mt-3 text-sm leading-6 text-blue-950">{focusShift}</p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-emerald-900">
              <Users className="h-4 w-4" />
              可调人数
            </div>
            <p className="mt-3 text-sm leading-6 text-emerald-950">{availableStaff.length} 人可安排</p>
          </div>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-950">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            今日缺口
          </div>
          <div className="space-y-3">
            {shiftGaps.map((item: any) => (
              <div
                key={`${item.store}-${item.shift}-${item.role}`}
                className="rounded-xl border border-stone-100 bg-stone-50 px-3 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-stone-950">{item.store}</div>
                    <div className="mt-1 text-xs text-stone-500">{item.shift}｜{item.role}</div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-xs ${
                    item.urgency === "高"
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {item.gap}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-950">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            优先补位
          </div>
          <div className="space-y-2">
            {recommendations.map((staff: string) => (
              <div
                key={staff}
                className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-950"
              >
                {staff}
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-950">
            <CalendarDays className="h-4 w-4 text-stone-500" />
            班次模板
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {shiftTemplates.slice(0, 4).map((shift: string) => (
              <div
                key={shift}
                className="rounded-xl border border-stone-100 bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700"
              >
                {shift}
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-950">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            排班提醒
          </div>
          <div className="space-y-2">
            {ruleAlerts.map((alert: string) => (
              <div
                key={alert}
                className="rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-xs leading-5 text-red-950"
              >
                {alert}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
