"use client";

import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowUpRight, CheckCircle2, LoaderCircle, ShieldAlert, ThumbsDown, ThumbsUp } from "lucide-react";
import { buildRestaurantDemo } from "@/lib/restaurant-demo";
import type { Message } from "@/lib/types";

type ChatKitPanelProps = {
  onAgentChange?: (agentName: string, context?: Record<string, any>) => void;
  onResponseEnd?: () => void;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const RESTAURANT_DEMO = buildRestaurantDemo();
const STARTER_PROMPTS = RESTAURANT_DEMO.starterPrompts;

function assistantTone(status: Message["status"]) {
  if (status === "blocked") {
    return {
      wrapper: "border-red-200 bg-red-50 text-red-950",
      badge: "bg-red-100 text-red-700",
      icon: <ShieldAlert className="h-4 w-4" />,
      label: "规则拦截",
    };
  }
  if (status === "warning") {
    return {
      wrapper: "border-amber-200 bg-amber-50 text-amber-950",
      badge: "bg-amber-100 text-amber-700",
      icon: <AlertTriangle className="h-4 w-4" />,
      label: "风险提醒",
    };
  }
  if (status === "success") {
    return {
      wrapper: "border-emerald-200 bg-emerald-50 text-emerald-950",
      badge: "bg-emerald-100 text-emerald-700",
      icon: <CheckCircle2 className="h-4 w-4" />,
      label: "已执行",
    };
  }
  return {
    wrapper: "border-stone-200 bg-white text-stone-900",
    badge: "bg-stone-100 text-stone-600",
    icon: null,
    label: "回复",
  };
}

function getDisplayAssistantName() {
  return "门店排班助手";
}

export function ChatKitPanel({
  onAgentChange,
  onResponseEnd,
}: ChatKitPanelProps) {
  const [messages, setMessages] = useState<Message[]>(RESTAURANT_DEMO.openingMessages);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function submitFeedback(messageId: string, value: 0 | 1) {
    const target = messages.find((message) => message.id === messageId);
    if (!target?.traceId) return;

    try {
      await fetch(`${API_BASE_URL}/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trace_id: target.traceId,
          value,
          comment: value === 1 ? "Helpful scheduling response" : "Needs review",
        }),
      });

      setMessages((prev) =>
        prev.map((message) =>
          message.id === messageId
            ? { ...message, feedbackSubmitted: value === 1 ? "up" : "down" }
            : message
        )
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "反馈提交失败，请稍后重试。";
      setError(message);
    }
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setDraft("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: trimmed,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      if (data.session_id) {
        setSessionId(data.session_id);
      }
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        agent: getDisplayAssistantName(),
        content: data.output_text || "已收到请求，但没有返回文本结果。",
        timestamp: new Date(),
        status: data.status ?? "info",
        traceId: data.trace_id ?? undefined,
        traceUrl: data.trace_url ?? undefined,
        feedbackSubmitted: null,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      onAgentChange?.(getDisplayAssistantName(), data.context ?? {});
      onResponseEnd?.();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "暂时没有连上排班服务，请稍后再试。";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-full min-h-[720px] flex-col rounded-[30px] border border-stone-200/80 bg-white/90 shadow-[0_24px_60px_rgba(70,53,35,0.08)] backdrop-blur">
        <div className="flex h-16 items-center rounded-t-[30px] border-b border-stone-200 bg-[linear-gradient(90deg,_#eb5e28,_#c4491d)] px-5 text-white">
        <div>
          <h2 className="text-sm font-semibold sm:text-base lg:text-lg">
            今天排哪家店
          </h2>
          <p className="text-xs text-white/80">
            说门店、班次和缺口，我来帮你梳理
          </p>
        </div>
      </div>
      <div className="flex flex-1 flex-col overflow-hidden bg-[linear-gradient(180deg,_rgba(255,250,245,0.8),_rgba(255,255,255,0.96))]">
        <div className="border-b border-stone-200/80 px-5 py-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm font-medium text-stone-900">常见排班请求</div>
            <div className="text-xs text-stone-500">门店 + 班次 + 缺口，越具体越好排</div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => void sendMessage(prompt)}
                className="rounded-full border border-stone-200 bg-white px-3 py-2 text-left text-xs text-stone-700 transition hover:border-stone-300 hover:bg-stone-50"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {(() => {
                const tone = assistantTone(message.status);
                return (
              <div
                className={`max-w-[85%] rounded-3xl px-4 py-3 shadow-sm ${
                  message.role === "user"
                    ? "bg-stone-950 text-white"
                    : `border ${tone.wrapper}`
                }`}
              >
                {message.role === "assistant" && message.agent ? (
                  <div className="mb-2 flex items-center gap-2">
                    <div className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium ${tone.badge}`}>
                      {tone.icon}
                      <span>{tone.label}</span>
                    </div>
                  </div>
                ) : null}
                <div className="whitespace-pre-wrap text-sm leading-7">
                  {message.content}
                </div>
                {message.role === "assistant" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void submitFeedback(message.id, 1)}
                      disabled={message.feedbackSubmitted !== null}
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${
                        message.feedbackSubmitted === "up"
                          ? "border-emerald-300 bg-emerald-100 text-emerald-700"
                          : "border-stone-200 bg-white text-stone-600"
                      } disabled:cursor-not-allowed`}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                      <span>有帮助</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void submitFeedback(message.id, 0)}
                      disabled={message.feedbackSubmitted !== null}
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${
                        message.feedbackSubmitted === "down"
                          ? "border-red-300 bg-red-100 text-red-700"
                          : "border-stone-200 bg-white text-stone-600"
                      } disabled:cursor-not-allowed`}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                      <span>没帮助</span>
                    </button>
                  </div>
                ) : null}
              </div>
                );
              })()}
            </div>
          ))}

          {isLoading ? (
            <div className="flex justify-start">
              <div className="inline-flex items-center gap-2 rounded-3xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-600 shadow-sm">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                正在核对门店缺口和可用伙伴...
              </div>
            </div>
          ) : null}

          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-stone-200/80 px-5 py-4">
          {error ? (
            <div className="mb-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft);
            }}
            className="flex items-end gap-3"
          >
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={`例如：${STARTER_PROMPTS[0]}`}
              rows={3}
              className="min-h-[72px] flex-1 resize-none rounded-3xl border border-stone-200 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-stone-400"
            />
            <button
              type="submit"
              disabled={isLoading || !draft.trim()}
              className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-stone-950 text-white transition hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"
            >
              <ArrowUpRight className="h-5 w-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
