"""ASPASIA PROMOTION — merkezi doğal-dil arayüzünün okuma/komut katmanı.

Mimari sözleşme:
- Aspasia = doğal-zekâ arayüzü (seyirci + açıklayıcı + komut formüle edici).
- Orchestrator Core = api.run_mission + PinealExecutor + TaskLifecycleRegistry
  (BURADAN YÖNETİLMEZ, BURAYA TAKLİT YAZILMAZ; yalnız dispatch ile tetiklenir).
- Agent planlaması = CognitiveRouter (SoT). Komut katmanı ajan listesi UYDURMAZ.
- Routing/kota/harcama yetkisi = LLMGateway + final_routing_policy. Bu modül
  yalnız okur; set_key/quota/spend/provider HTTP mutasyonu YAPMAZ ve YAPAMAZ.
"""
from __future__ import annotations

import contextlib
import os
import re
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent_core.services import final_routing_policy as policy
from agent_core.services.cognitive_router import GOAL_FOCUS

# Goal sozlesmesi COGNITIVE_ROUTER'da turetilir (tek kaynak); Aspasia kendi
# vocabulariesini ICATMAZ — Literal, gercek GOAL_FOCUS anahtarlarindan olusur.
_GOAL_IDS = tuple(GOAL_FOCUS.keys())

# ---------------------------------------------------------------- inspectors


class RoutingInspector:
    """Read-only explanation of the agent-chain + provider cost ladder."""

    def __init__(self, gateway: Any):
        self._gateway = gateway

    def explain(self, agent_name: str, task: str = "dialogue") -> Dict[str, Any]:
        gw = self._gateway
        chain: List[str] = []
        try:
            chain = list(gw.get_agent_chain(agent_name, task))
        except Exception as exc:  # pragma: no cover - defensive read
            return {"agent": agent_name, "error": f"{type(exc).__name__}: {exc}"[:140]}
        env_var = f"OPENROUTER_AGENT_CHAIN_{agent_name.upper()}"
        if os.getenv(env_var):
            source = "env_override"
        elif agent_name in getattr(gw, "AGENT_CHAINS", {}):
            source = "agent_matrix"
        else:
            source = "task_chain"
        variants: List[Dict[str, Any]] = []
        if chain:
            first = chain[0]
            try:
                for route in gw.agent_route_variants(first):
                    if route is None:
                        variants.append({
                            "route_key": f"{first}@openrouter",
                            "provider": "openrouter",
                            "endpoint": getattr(gw, "openrouter_base_url", ""),
                            "pricing": gw.MODEL_PRICING.get(first),
                            "tier": "pool-provider",
                        })
                    else:
                        entry = {
                            "route_key": f"{route.model}@{route.provider_id}",
                            "provider": route.provider_id,
                            "endpoint": route.base_url,
                            "pricing": route.pricing,
                            "tier": (
                                "free" if not route.pricing
                                or (route.pricing["in"] == 0 and route.pricing["out"] == 0)
                                else "paid"
                            ),
                        }
                        if route.list_input_per_million_usd:
                            entry["list_pricing"] = {
                                "in": route.list_input_per_million_usd,
                                "out": route.list_output_per_million_usd,
                            }
                            entry["discount_pct"] = round(
                                (1.0 - route.input_per_million_usd / route.list_input_per_million_usd)
                                * 100.0, 1
                            )
                        variants.append(entry)
            except Exception as exc:  # pragma: no cover
                variants.append({"error": f"{type(exc).__name__}: {exc}"[:120]})
        return {
            "agent": agent_name,
            "task": task,
            "chain": chain,
            "chain_source": source,
            "selected": variants[0] if variants else None,
            "alternatives": variants[1:],
            "fallback_rule": (
                "gecici hata -> siradaki rota, o biterse siradaki model; "
                "spend-cap/paid-escalation/unknown-pricing/substitution reddi -> ZINCIR DURUR"
            ),
        }


class TelemetryReader:
    """Bounded view over the gateway call log; no parallel telemetry store."""

    _FIELDS = (
        "call_id", "model", "requested_model", "actual_model", "provider",
        "route_key", "fallback_reason", "chain_source", "quota_status",
        "error", "duration_ms", "cost_usd", "agent_id",
    )

    def __init__(self, gateway: Any, limit: int = 40):
        self._gateway = gateway
        self._limit = limit

    def recent(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for record in list(getattr(self._gateway, "call_log", []))[-self._limit:]:
            if agent_id and record.get("agent_id") != agent_id:
                continue
            rows.append({k: record.get(k) for k in self._FIELDS if record.get(k) is not None})
        return rows

    def anomalies(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"fallbacks": [], "substitution_denials": [], "model_mismatches": []}
        denial_re = re.compile(
            r"MODEL_SUBSTITUTION_DENIED: requested '([^']+)' but provider returned '([^']+)'"
        )
        for record in list(getattr(self._gateway, "call_log", []))[-self._limit:]:
            if record.get("fallback_reason"):
                out["fallbacks"].append({
                    "model": record.get("model"),
                    "provider": record.get("provider"),
                    "reason": record.get("fallback_reason"),
                })
            error_text = str(record.get("error", ""))
            if "MODEL_SUBSTITUTION_DENIED" in error_text:
                match = denial_re.search(error_text)
                # STRUCTURED field once (ROUTING-HARDENING); eski kayitlarda
                # error-metin regex'i fallback'tir — hicbir alan uydurulmaz.
                out["substitution_denials"].append({
                    "model": record.get("model"),
                    "provider": record.get("provider"),
                    "requested_model": (record.get("requested_model")
                                        or (match.group(1) if match else None)),
                    "actual_model": (match.group(2) if match
                                     else record.get("actual_model")),
                })
            requested = record.get("requested_model")
            actual = record.get("actual_model")
            if requested and actual and requested != actual:
                out["model_mismatches"].append({"requested": requested, "actual": actual,
                                                "provider": record.get("provider")})
        return out


class QuotaReader:
    """Reads the QuotaGovernor + policy QUOTAS; unknown stays 'unknown'."""

    def __init__(self, governor: Any = None, gateway: Any = None):
        self._governor = governor
        self._gateway = gateway

    def _gov(self):
        if self._governor is None:
            accessor = getattr(self._gateway, "_quota_governor", None)
            if not callable(accessor):
                # GOZLEM DURUMUNUN TEK SoT'U gateway governor'idir. Bos bir
                # governor UYDURMAK "HEALTHY" demek olurdu -> unavailable.
                return None
            self._governor = accessor()
        return self._governor

    def snapshot(self, provider: str) -> Dict[str, Any]:
        limits: Dict[str, Any] = {}
        for dim, value in policy.QUOTAS.get(provider, {}).items():
            limits[dim] = "unknown" if value in (None, policy.QUOTA_UNKNOWN) else value
        gov = self._gov()
        if gov is None:
            status, remaining, source = "unavailable", None, None
        else:
            try:
                snap = gov.snapshot(provider)
                status = getattr(snap.status, "name", str(snap.status))
                remaining = getattr(snap, "remaining_fraction", None)
                source = getattr(snap, "source", None)
            except Exception:  # pragma: no cover
                status, remaining, source = "unavailable", None, None
        return {
            "provider": provider,
            "limits": limits,
            "status": status,
            "remaining_fraction": remaining,
            "source": source,
            "note": "unknown limits are NEVER treated as unlimited (fail-closed doctrine)",
        }


class CostReader:
    """Budget snapshot + effective-vs-list pricing (Nous doctrine)."""

    def __init__(self, gateway: Any):
        self._gateway = gateway

    def snapshot(self) -> Dict[str, Any]:
        try:
            return dict(self._gateway.budget_status())
        except Exception as exc:  # pragma: no cover
            return {"error": f"{type(exc).__name__}"}

    def pricing_overview(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for key, spec in policy.ROUTES.items():
            row = {
                "route_key": key,
                "model": spec.model,
                "provider": spec.provider,
                "tier": spec.tier,
                "effective": {"in": spec.input_per_million_usd, "out": spec.output_per_million_usd},
            }
            if spec.list_input_per_million_usd is not None:
                row["list"] = {"in": spec.list_input_per_million_usd,
                               "out": spec.list_output_per_million_usd}
                row["discount_pct"] = round(
                    (1.0 - spec.input_per_million_usd / spec.list_input_per_million_usd) * 100.0, 1
                )
            rows.append(row)
        return rows


class AgentInspector:
    """Reads the REAL registry (executor.agents) + lifecycle snapshot."""

    def __init__(self, executor: Any = None):
        self._executor = executor

    def registry(self) -> List[str]:
        agents = getattr(self._executor, "agents", {}) or {}
        return sorted(agents.keys())

    def run_status(self, room_state: Any) -> Dict[str, Any]:
        if not isinstance(room_state, dict):
            return {"state": "no-room"}
        active = room_state.get("active_tasks") or {}
        if not active:
            return {"state": "idle"}
        snapshot = list(active.values())[-1]
        if not isinstance(snapshot, dict):
            snapshot = {
                "task_id": getattr(snapshot, "task_id", None),
                "status": getattr(snapshot, "status", None),
                "planned_agents": getattr(snapshot, "planned_agents", []),
                "completed_agents": getattr(snapshot, "completed_agents", []),
                "current_agent": getattr(snapshot, "current_agent", None),
                "agent_runs": getattr(snapshot, "agent_runs", {}),
            }
        raw_status = snapshot.get("status")
        return {
            "task_id": snapshot.get("task_id"),
            "status": raw_status,
            # Faz-6: snapshot terminal durumdaysa ARTIK CANLI degildir;
            # canliyi "bayat" diye etiketle — Aspasia kanonik kaynaga yonlendirilir.
            "is_final": str(getattr(raw_status, "value", raw_status)) in FINAL_TASK_STATUSES,
            "planned": snapshot.get("planned_agents") or [],
            "completed": snapshot.get("completed_agents") or [],
            "current": snapshot.get("current_agent"),
            "runs": {
                name: {"status": run.get("status") if isinstance(run, dict) else
                       getattr(run, "status", None)}
                for name, run in (snapshot.get("agent_runs") or {}).items()
            },
        }


# ---------------------------------------------------------------- commands

class AspasiaIntent(BaseModel):
    """LLM-uretimli YAPILANDIRILMIS niyet sozlesmesi.

    extra='forbid': model/provider/quota gibi alanlar UYDURULAMAZ — routing
    ve planlama yetkisi Aspasia'da degildir (CognitiveRouter + LLMGateway SoT).
    `goals`: kullanicinin AMACI tasir (semantic plan), AJAN LISTESI degil —
    ajan secimi CognitiveRouter'ın kanit/kabiliyet kapilarinda kalir.
    """

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(default="none", pattern="^(none|explain_status|run_profile_analysis)$")
    target_url: Optional[str] = None
    rationale: Optional[str] = None
    goals: List[Literal[_GOAL_IDS]] = Field(default_factory=list)


# Hedef dogrulama: yalnizca mevcut scraper sozlesmesinin gercek host'lari.
# (Ornek-uydurmama doktrini [009]: placeholder veri ASLA uretilmez.)
_TARGET_RE = re.compile(r"^https://(www\.)?(instagram\.com|instagr\.am)/[A-Za-z0-9._@-]{1,64}/?$")

_GOAL_DOC = "\n".join(f'- "{g}": {", ".join(agents)}' for g, agents in GOAL_FOCUS.items())

_INTENT_INSTRUCTION = (
    "Kullanicinin cumlesini siniflandir. Yalniz su niyetler gecerlidir:\n"
    '- "run_profile_analysis": kullanici belirli bir Instagram profilini inceletmek istiyor '
    've mesajda acik bir profil URL\'i var -> target_url alanina BIREBIR URL yaz.\n'
    '- "explain_status": kullanici sistem/ajan/analiz durumu hakkinda bilgi istiyor.\n'
    '- "none": hicbiri.\n'
    "URL mesajda ACIKCA yoksa uydurma; intent='none' dondur.\n\n"
    "goals: kullanicinin AMACINI tasir; AJAN ISMI YAZMAZSIN. Gecerli goal id'leri "
    "(baska isim UYDURMA; message'da acik karsiligi yoksa hic goal ekleme):\n"
    + _GOAL_DOC + "\n"
    "Ornek: 'cümlesinde çelişki arıyorsa' -> contradiction_detection. "
    "Ek odak yoksa goals: [\"profile_analysis\"].\n\n"
    "JSON:\n"
    '{{"intent": "...", "target_url": null, "rationale": "tek cümle", '
    '"goals": ["..."]}}\n\n'
    "KULLANICI MESAJI:\n{text}\n"
)


class AspasiaCommandResult(BaseModel):
    command_id: str
    accepted: bool
    intent: str
    task_id: Optional[str] = None
    reason: Optional[str] = None


class AspasiaCommandGateway:
    """Single sanctioned WRITE path for Aspasia: intent -> validation -> dispatch.

    `dispatch(spec: dict) -> Optional[str]` is injected by the real orchestrator
    wiring (api.py) and MUST route through the same task-launch path a human
    uses (/api/initiate semantics): rate limits, lifecycle transitions,
    executor planning. This gateway holds no provider client, no key, no
    quota/spend mutation surface.
    """

    def __init__(self, dispatch: Callable[[Dict[str, Any]], Optional[str]], *, gateway: Any = None):
        self._dispatch = dispatch
        self._gateway = gateway
        self._audit: deque[Dict[str, Any]] = deque(maxlen=64)

    # -- audit ---------------------------------------------------------
    def audit(self) -> List[Dict[str, Any]]:
        return list(self._audit)

    def _record(self, **fields: Any) -> Dict[str, Any]:
        entry = {"created_at": datetime.now(timezone.utc).isoformat(), **fields}
        self._audit.append(entry)
        return entry

    # -- submit --------------------------------------------------------
    async def submit(self, user_message: str, client_id: str = "default") -> AspasiaCommandResult:
        command_id = uuid.uuid4().hex[:12]
        gateway = self._gateway
        if gateway is None:
            self._record(command_id=command_id, status="rejected", reason="gateway_unavailable")
            return AspasiaCommandResult(
                command_id=command_id, accepted=False, intent="none",
                reason="gateway_unavailable",
            )
        try:
            # Niyet cikarimi AYNI routing yiginindan gecer (aspasia chain'i,
            # provider merdiveni, spend/quota gate'leri) — ayrica bir "akilli
            # LLM cagrisi" kanali ACILMAZ. Cagri, MEVCUT capture_calls kapsami
            # altinda agent_id=aspasia ile etiketlenir (paralel telemetri yok).
            capture = getattr(gateway, "capture_calls", None)
            scope_ctx = capture(None, "aspasia") if callable(capture) else contextlib.nullcontext()
            with scope_ctx:
                intent: AspasiaIntent = await gateway.query_json_chain(
                    prompt=_INTENT_INSTRUCTION.format(text=(user_message or "")[:1200]),
                    schema=AspasiaIntent,
                    task="dialogue",
                    agent_name="aspasia",
                )
        except Exception as exc:
            self._record(command_id=command_id, status="intent_unavailable",
                         error=f"{type(exc).__name__}"[:80])
            return AspasiaCommandResult(
                command_id=command_id, accepted=False, intent="none",
                reason="intent_unavailable",
            )

        if intent.intent == "none":
            self._record(command_id=command_id, status="no_action", intent="none")
            return AspasiaCommandResult(command_id=command_id, accepted=True,
                                        intent="none", reason="no_action")
        if intent.intent == "explain_status":
            self._record(command_id=command_id, status="read_only", intent=intent.intent)
            return AspasiaCommandResult(command_id=command_id, accepted=True,
                                        intent=intent.intent, reason="read_only")
        # run_profile_analysis — TEK yazma eylemi; hedef dogrulama sart.
        url = (intent.target_url or "").strip()
        if not _TARGET_RE.match(url):
            self._record(command_id=command_id, status="rejected", intent=intent.intent,
                         reason="unsupported_or_missing_target")
            return AspasiaCommandResult(command_id=command_id, accepted=False,
                                        intent=intent.intent,
                                        reason="unsupported_or_missing_target")
        try:
            task_id = self._dispatch({
                "client_id": client_id,
                "target_url": url,
                # AMAC KAYBI FIX: goal'lar dispatch'e aynen tasinir; plan
                # yetkisi CognitiveRouter'da kalir (goal != agent listesi).
                "goals": list(intent.goals),
            })
        except Exception as exc:
            self._record(command_id=command_id, status="dispatch_failed",
                         intent=intent.intent, error=f"{type(exc).__name__}"[:80])
            return AspasiaCommandResult(command_id=command_id, accepted=False,
                                        intent=intent.intent, reason="dispatch_failed")
        self._record(command_id=command_id, status="dispatched", intent=intent.intent,
                     task_id=task_id, goals=list(intent.goals),
                     target_host=re.sub(r"^https://", "", url).split("/")[0])
        return AspasiaCommandResult(command_id=command_id, accepted=True,
                                    intent=intent.intent, task_id=task_id)


# Kanonik sonuc icin terminal durumlar (PipelineStatus degerleri) — snapshot
# bunlardan birindeyse ARTIK CANLI degildir; kanonik kaynak CanonicalMemory'dir.
FINAL_TASK_STATUSES = {
    "completed", "partially_completed", "halted_evidence", "halted_critical",
    "halted_frequency", "failed",
}


class MissionResultReader:
    """CanonicalMemory uzerinden salt-okur sonuc ozeti — PARALEL STORE YOK.

    Corrupted kanonik kayit sessizce 'bos' sayilmaz (fail-closed bellek
    sozlesmesi): 'corrupted' doner, Aspasia kullaniciya kurtarma gerekir der.
    """

    @staticmethod
    def latest_task_id(room_state: Any) -> Optional[str]:
        if not isinstance(room_state, dict):
            return None
        active = room_state.get("active_tasks") or {}
        if not active:
            return None
        return list(active.keys())[-1]

    @staticmethod
    def latest_finished_task_id(room_state: Any) -> Optional[str]:
        if not isinstance(room_state, dict):
            return None
        active = room_state.get("active_tasks") or {}
        for task_id in reversed(list(active.keys())):
            snap = active[task_id]
            status = (snap.get("status") if isinstance(snap, dict)
                      else getattr(snap, "status", None))
            if str(getattr(status, "value", status)) in FINAL_TASK_STATUSES:
                return task_id
        return None

    def read(self, executor: Any, task_id: Optional[str]) -> Dict[str, Any]:
        if not task_id:
            return {"state": "no-task"}
        memory = getattr(executor, "memory", None)
        getter = getattr(memory, "get_task_memory", None)
        if not callable(getter):
            return {"state": "unsupported"}
        try:
            doc = getter(task_id)
        except Exception as exc:
            return {"state": "corrupted",
                    "error": f"{type(exc).__name__}: {str(exc)[:100]}"}
        if not doc:
            # Eksik dosya = bos hafiza (CanonicalMemory sozlesmesi), uydurma yok.
            return {"state": "missing", "task_id": task_id}
        evidence = doc.get("evidence") or []
        agents = sorted({
            e.get("agent") for e in evidence
            if isinstance(e, dict) and e.get("agent")
        })
        return {
            "state": "ok",
            "task_id": doc.get("task_id", task_id),
            "last_updated": doc.get("last_updated"),
            "overall_confidence": doc.get("confidence"),
            "evidence_count": len(evidence),
            "agents": agents,
        }


def build_oversight_digest(
    gateway: Any,
    room_state: Any = None,
    executor: Any = None,
    command_gateway: Optional[AspasiaCommandGateway] = None,
    last_agent: Optional[str] = None,
) -> str:
    """Compact, source-backed state block for the ASPASIA system prompt.

    Dürüstlük kurali: satir yalnizca OKUNABILIR kanit varsa eklenir. "veri
    yok" satirlari bloku gürültüleme; hic içerik yoksa bos string döner ve
    chat() DENETİM bloğunu hic açmaz (uydurma digest yok).
    """
    lines: List[str] = []
    has_content = False
    try:
        routing = RoutingInspector(gateway).explain(last_agent or "friction_detector")
        chain = routing.get("chain") or []
        if chain:
            has_content = True
            selected = routing.get("selected") or {}
            lines.append(
                "ROUTING[" + str(routing.get("agent")) + "]: "
                f"chain={'>'.join(chain)} kaynak={routing.get('chain_source')}"
                + (f" secilen={selected.get('route_key')} ucan={selected.get('endpoint')}"
                   if selected else "")
                + (f" indirim={selected.get('discount_pct')}%" if selected.get("discount_pct") else "")
            )
    except Exception:  # pragma: no cover
        pass
    try:
        anomalies = TelemetryReader(gateway).anomalies()
        counts = {k: len(v) for k, v in anomalies.items()}
        if any(counts.values()):
            has_content = True
            lines.append(
                "TELEMETRI: fallback={fallbacks} substitution={substitution_denials} "
                "uyusmazlik={model_mismatches}".format(**counts)
            )
        # Faz-5: requested != actual AYRINTISI chat'e tasinir (call_log'dan
        # okunur; yeni store yok) — reddedilen ikame aciklanabilir olmali.
        for denial in anomalies["substitution_denials"][-2:]:
            lines.append(
                "SUBSTITUTION DENIED: istenen='" + str(denial.get("requested_model"))
                + "' saglayici dondurdu='" + str(denial.get("actual_model"))
                + "' (" + str(denial.get("provider")) + ") — ikame reddedildi, zincir durdu"
            )
    except Exception:  # pragma: no cover
        pass
    try:
        snap = CostReader(gateway).snapshot()
        if "error" not in snap:
            has_content = True
            lines.append(
                f"MALİYET: harcama=${snap.get('spend_usd', 0):.4f} rezerve=${snap.get('reserved_usd', 0):.4f} "
                f"limit={'sinirsiz' if not snap.get('cap_usd') else '$%.2f' % snap.get('cap_usd', 0)}"
            )
    except Exception:  # pragma: no cover
        pass
    try:
        quotas = []
        for provider in ("groq", "cerebras"):
            q = QuotaReader(gateway=gateway).snapshot(provider)
            if q["status"] not in ("unknown", "unavailable"):
                has_content = True
            quotas.append(f"{provider}:{q['status']}" + (
                f" kalan={round(q['remaining_fraction'] * 100)}%"
                if q.get("remaining_fraction") is not None else ""
            ))
        if quotas and has_content:
            lines.append("KOTA: " + " | ".join(quotas))
    except Exception:  # pragma: no cover
        pass
    try:
        # ROUTING-HARDENING: saglayici saglik devresi gorunur (gateway'in kendi
        # durumu okunur; yeni store yok). Bos ise satir eklenmez — gurultu yok.
        ph = getattr(gateway, "provider_health", None)
        if callable(ph):
            cooling = {k: v for k, v in ph().items() if v and v > 0}
            if cooling:
                has_content = True
                lines.append("SAĞLIK: " + " | ".join(
                    f"{p} cooldown={s:.0f}s" for p, s in sorted(cooling.items())))
    except Exception:  # pragma: no cover
        pass
    if executor is not None:
        try:
            status = AgentInspector(executor).run_status(room_state)
            if status.get("state") not in (None, "no-room", "idle") or status.get("task_id"):
                has_content = True
                stale = " [BAYAT-snapshot; kanonik: CanonicalMemory]" if status.get("is_final") else ""
                lines.append(
                    f"TASK: {status.get('task_id', '-')} durum={status.get('status', 'idle')} "
                    f"tamamlanan={len(status.get('completed') or [])}/{len(status.get('planned') or [])}"
                    + stale
                )
            # Faz-3/4: sonuc dongusu — kanonik hafiza OKUNUR (paralel store yok).
            finished = MissionResultReader.latest_finished_task_id(room_state)
            if finished:
                result = MissionResultReader().read(executor, finished)
                if result.get("state") == "ok":
                    has_content = True
                    conf = result.get("overall_confidence")
                    lines.append(
                        f"SONUÇ[{result.get('task_id')}]: güven={'%.2f' % conf if isinstance(conf, (int, float)) else '?'} "
                        f"kanıt={result.get('evidence_count')} "
                        f"ajanlar={','.join(result.get('agents') or []) or '-'} (CanonicalMemory)"
                    )
                elif result.get("state") == "corrupted":
                    has_content = True
                    lines.append(
                        "SONUÇ: kanonik hafıza BOZUK — analiz özetlenemez, açık kurtarma gerekir "
                        f"({result.get('error')})"
                    )
                elif result.get("state") == "missing":
                    has_content = True
                    lines.append("SONUÇ: kanonik kayıt yok — görev henüz mühürlenmemiş olabilir")
        except Exception:  # pragma: no cover
            pass
    if command_gateway is not None:
        for entry in command_gateway.audit()[-3:]:
            has_content = True
            lines.append(
                f"KOMUT {entry.get('command_id')}: {entry.get('status')}"
                + (f" task={entry.get('task_id')}" if entry.get("task_id") else "")
                + (f" ({entry.get('reason')})" if entry.get("reason") else "")
            )
    return "\n".join(lines) if has_content else ""
