import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { getAccessToken } from "../auth/getAccessToken";
import { getObservabilityConversation, ObservabilityRequestError } from "../api/observability";
import type { ConversationDetailResult, RunDetail } from "../api/observability";
import "./observability.css";

interface ObservabilityConversationDetailPageProps {
  instance: IPublicClientApplication;
  account: AccountInfo;
}

function unavailable(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === "" ? "No disponible" : String(value);
}

export function ObservabilityConversationDetailPage({
  instance,
  account,
}: ObservabilityConversationDetailPageProps) {
  const { conversationId } = useParams<{ conversationId: string }>();
  const [detail, setDetail] = useState<ConversationDetailResult | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;

    async function load(): Promise<void> {
      setIsLoading(true);
      setErrorStatus(null);
      try {
        const accessToken = await getAccessToken(instance, account);
        const result = await getObservabilityConversation(accessToken, conversationId as string);
        if (cancelled) return;
        setDetail(result);
        setSelectedRunId(result.runs.length > 0 ? result.runs[result.runs.length - 1].runId : null);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ObservabilityRequestError) {
          setErrorStatus(error.status);
        } else {
          console.error("Observability conversation detail load failed:", error);
          setErrorStatus(0);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const selectedRun: RunDetail | null =
    detail?.runs.find((run) => run.runId === selectedRunId) ?? null;

  return (
    <main className="observability-detail">
      <div className="observability-detail__breadcrumb">
        <Link to="/observability">← Volver al dashboard</Link>
      </div>

      {isLoading && <p>Cargando…</p>}
      {errorStatus === 404 && <p className="observability-dashboard__error">Conversación no encontrada.</p>}
      {errorStatus === 403 && (
        <p className="observability-dashboard__error">No tienes autorización para ver Observability.</p>
      )}
      {errorStatus !== null && errorStatus !== 404 && errorStatus !== 403 && (
        <p className="observability-dashboard__error">No se pudo cargar la conversación.</p>
      )}

      {!isLoading && detail && (
        <div className="observability-detail__panels">
          <section className="observability-detail__panel observability-detail__panel--left">
            <h2>Conversación</h2>
            <ul className="observability-detail__messages">
              {detail.messages.map((message) => (
                <li
                  key={message.id}
                  className={`observability-detail__message observability-detail__message--${message.role}`}
                >
                  <div className="observability-detail__message-meta">
                    <span>{message.role}</span>
                    <span>{new Date(message.createdAt).toLocaleTimeString()}</span>
                  </div>
                  <div className="observability-detail__message-text">{message.content}</div>
                  {message.runId && (
                    <button
                      type="button"
                      className={`observability-detail__run-link${
                        message.runId === selectedRunId ? " observability-detail__run-link--active" : ""
                      }`}
                      onClick={() => setSelectedRunId(message.runId)}
                    >
                      Ver run {message.runId.slice(0, 8)}…
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="observability-detail__panel observability-detail__panel--center">
            <h2>Run seleccionado</h2>
            {selectedRun ? <RunDetailView run={selectedRun} /> : <p>No hay un run seleccionado.</p>}
          </section>

          <section className="observability-detail__panel observability-detail__panel--right">
            <h2>Línea de tiempo</h2>
            {selectedRun ? <RunTimeline run={selectedRun} /> : <p>No hay un run seleccionado.</p>}
          </section>
        </div>
      )}
    </main>
  );
}

function RunDetailView({ run }: { run: RunDetail }) {
  return (
    <dl className="observability-detail__fields">
      <dt>Intención detectada</dt>
      <dd>{unavailable(run.detectedIntent)}</dd>
      <dt>Confianza de intención</dt>
      <dd>{unavailable(run.intentConfidence)}</dd>
      <dt>Agente seleccionado</dt>
      <dd>{unavailable(run.selectedAgent)}</dd>
      <dt>Razón de enrutamiento</dt>
      <dd>{unavailable(run.routingReason)}</dd>
      <dt>Estado</dt>
      <dd>{unavailable(run.finalStatus)}</dd>
      <dt>Modelo</dt>
      <dd>{unavailable(run.model)}</dd>
      <dt>Tokens de entrada</dt>
      <dd>{unavailable(run.inputTokens)}</dd>
      <dt>Tokens de salida</dt>
      <dd>{unavailable(run.outputTokens)}</dd>
      <dt>Costo estimado (USD)</dt>
      <dd>{run.estimatedCostUsd === null ? "No disponible" : `$${run.estimatedCostUsd.toFixed(4)}`}</dd>
      <dt>Versión del catálogo de precios</dt>
      <dd>{unavailable(run.pricingSnapshotVersion)}</dd>
      <dt>Latencia total</dt>
      <dd>{run.totalLatencyMs === null ? "No disponible" : `${Math.round(run.totalLatencyMs)} ms`}</dd>
      <dt>Reintentos / iteraciones</dt>
      <dd>{unavailable(run.iterations)}</dd>

      <dt>Llamadas a herramientas</dt>
      <dd>
        {run.toolCalls.length === 0 ? (
          "Ninguna"
        ) : (
          <ul className="observability-detail__tool-calls">
            {run.toolCalls.map((call) => (
              <li key={call.callId}>
                <strong>{call.toolName}</strong> — {call.success ? "éxito" : "falló"}
                {call.errorType ? ` (${call.errorType})` : ""}
                {call.latencyMs !== null ? ` — ${Math.round(call.latencyMs)} ms` : ""}
              </li>
            ))}
          </ul>
        )}
      </dd>
    </dl>
  );
}

function RunTimeline({ run }: { run: RunDetail }) {
  const events: string[] = [
    `Mensaje recibido — ${new Date(run.createdAt).toLocaleTimeString()}`,
  ];
  if (run.selectedAgent) {
    events.push(`Agente seleccionado: ${run.selectedAgent}`);
  }
  for (const call of run.toolCalls) {
    events.push(
      `Herramienta ejecutada: ${call.toolName} (${call.success ? "éxito" : "falló"}${
        call.latencyMs !== null ? `, ${Math.round(call.latencyMs)} ms` : ""
      })`,
    );
  }
  if (run.stoppedDueToTimeout) {
    events.push("Detenido por timeout");
  }
  if (run.stoppedDueToMaxIterations) {
    events.push("Detenido por máximo de iteraciones");
  }
  events.push(`Completado — estado: ${unavailable(run.finalStatus)}`);

  return (
    <ol className="observability-detail__timeline">
      {events.map((event, index) => (
        <li key={index}>{event}</li>
      ))}
    </ol>
  );
}
